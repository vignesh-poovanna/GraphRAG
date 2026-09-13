"""
pipeline.py — Phase 8 (IP-SAKTI Sahayak)

Speech-to-Speech pipeline with smart barge-in interruption and session memory.

Flow:
  Mic → VAD → STT (faster-whisper) → [Hindi→EN translation] →
  Orchestrator (Cerebras classify + Groq synthesise) →
  TTS (kokoro-onnx) → Speaker

Barge-in (smart interruption):
  1. While TTS is playing, VAD runs on the mic in a background thread.
  2. If speech is detected above threshold → set _interrupt flag.
  3. TTS playback loop checks _interrupt and stops mid-sentence.
  4. Partial answer + turn index saved to SessionCache.
  5. STT transcribes the new utterance; session history is loaded as context.
  6. Orchestrator receives the last 4 turns → answer is context-aware.

Hindi→English:
  If langdetect → 'hi' (or 'mr', 'bn', etc.), we translate via Groq before
  hitting the vector DB. This keeps the corpus query in English while still
  accepting Hindi voice input. Answer is returned in English (TTS speaks English).

Usage:
    from src.speech.pipeline import SpeechPipeline
    p = SpeechPipeline(orchestrator, config)
    p.run()           # blocking voice loop
"""

import logging
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from src.speech.session_cache import SessionCache

logger = logging.getLogger(__name__)

# Audio constants
SAMPLE_RATE  = 16000
CHANNELS     = 1
BLOCK_FRAMES = 512          # ~32 ms per block at 16 kHz
MAX_RECORD_S = 30           # max utterance length before auto-stop


class SpeechPipeline:
    """
    Voice loop with barge-in interruption and cached session memory.

    Args:
        orchestrator: Orchestrator instance (already initialised)
        config:       Config instance
        session_id:   Pass an existing session ID to resume a conversation
    """

    def __init__(self, orchestrator, config, session_id: str = None):
        self.orch   = orchestrator
        self.config = config

        # Session memory
        db_path = config.get("speech.session_cache", "./data/session_cache.db")
        self.cache   = SessionCache(db_path)
        self.session = self.cache.new_session(session_id)

        # STT
        self._stt_model  = None   # lazy-loaded
        self._stt_name   = config.get("speech.stt_model",  "base")
        self._stt_device = config.get("speech.stt_device", "cpu")

        # TTS
        self._tts = None          # lazy-loaded
        self._tts_voice = config.get("speech.tts_voice", "af_heart")
        self._tts_speed = config.get("speech.tts_speed", 1.0)

        # VAD
        self._vad_model    = None
        self._vad_utils    = None
        self._vad_thresh   = config.get("speech.vad_threshold", 0.5)
        self._interrupt    = threading.Event()
        self._audio_q      = queue.Queue()

        # Groq translation (Hindi → EN)
        self._synthesis_api_key  = config.get("llm.synthesis_api_key", "")
        self._synthesis_base_url = config.get("llm.synthesis_base_url", "https://api.groq.com/openai/v1")
        self._synthesis_model    = config.get("llm.synthesis_model", "llama-3.1-8b-instant")

        logger.info("SpeechPipeline ready (session=%s)", self.session)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self):
        """Blocking voice loop. Press Ctrl-C to exit."""
        print(f"\n🎙️  IP-SAKTI Sahayak — Voice Mode  (session: {self.session[:8]}...)")
        print("   Speak your query. Interrupt me at any time by speaking again.\n")
        try:
            while True:
                self._one_turn()
        except KeyboardInterrupt:
            print("\n👋  Voice session ended.")

    def query(self, text: str, client_history: list = None) -> dict:
        """
        Non-voice entry point: accepts text directly and returns result dict.
        client_history: last 3 turns from the browser's sessionStorage
                        [{role, content}, ...] — cleared on page refresh.
        """
        # Prefer client-supplied history (fresher, capped at 3); fall back to DB
        if client_history:
            history = client_history[-3:]
        else:
            history = self.cache.get_history(self.session, last_n=3)
        translated, lang = self._maybe_translate(text)
        self.cache.add_turn(self.session, "user", text)

        result = self.orch.run(translated, session_context=history)
        self.cache.add_turn(self.session, "assistant", result.get("answer", ""))
        result["language"] = lang
        return result

    # ------------------------------------------------------------------
    # One voice turn
    # ------------------------------------------------------------------

    def _one_turn(self):
        """Listen → transcribe → translate → answer → speak → repeat."""
        print("🎤  Listening…")
        audio = self._record_until_silence()
        if audio is None or len(audio) < SAMPLE_RATE * 0.5:
            return   # too short to be a real utterance

        text = self._transcribe(audio)
        if not text or not text.strip():
            return

        print(f"📝  You said: {text}")
        translated, lang = self._maybe_translate(text)
        if translated != text:
            print(f"🔄  Translated (→ EN): {translated}")

        self.cache.add_turn(self.session, "user", text)
        history = self.cache.get_history(self.session, last_n=4)

        print("🤔  Thinking…")
        result = self.orch.run(translated, session_context=history)
        answer = result.get("answer", "")
        print(f"💬  Answer: {answer}\n")

        self.cache.add_turn(self.session, "assistant", answer)
        self._speak(answer)

    # ------------------------------------------------------------------
    # STT
    # ------------------------------------------------------------------

    def _load_stt(self):
        if self._stt_model is None:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper model '%s' on %s", self._stt_name, self._stt_device)
            self._stt_model = WhisperModel(
                self._stt_name,
                device=self._stt_device,
                compute_type="int8",
            )

    def _transcribe(self, audio: np.ndarray) -> str:
        self._load_stt()
        segments, _ = self._stt_model.transcribe(
            audio.astype(np.float32),
            beam_size=3,
            language=None,   # auto-detect
        )
        return " ".join(s.text for s in segments).strip()

    # ------------------------------------------------------------------
    # Hindi → English translation
    # ------------------------------------------------------------------

    def _maybe_translate(self, text: str) -> tuple:
        """
        Returns (translated_text, detected_lang).
        If lang is 'en', returns text unchanged.
        Translation uses Groq (already configured) — single short call.
        Non-English input is translated to English before hitting the retrieval stack.
        """
        try:
            from langdetect import detect
            lang = detect(text[:300])
        except Exception:
            lang = "en"

        if lang == "en":
            return text, lang

        # Translate via Groq
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self._synthesis_api_key,
                base_url=self._synthesis_base_url,
            )
            resp = client.chat.completions.create(
                model=self._synthesis_model,
                messages=[
                    {"role": "system", "content": "Translate the following text to English. Return ONLY the translated text, no explanations."},
                    {"role": "user",   "content": text},
                ],
                temperature=0.0,
                max_tokens=300,
            )
            translated = resp.choices[0].message.content.strip()
            logger.info("Translated '%s' → '%s'", lang, "en")
            return translated, lang
        except Exception as e:
            logger.warning("Translation failed (%s); using original", e)
            return text, lang

    # ------------------------------------------------------------------
    # TTS with barge-in
    # ------------------------------------------------------------------

    def _load_tts(self):
        if self._tts is None:
            from kokoro_onnx import Kokoro
            logger.info("Loading Kokoro TTS")
            self._tts = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

    def _speak(self, text: str):
        """
        Synthesise and play audio, checking for barge-in interruption.
        Splits answer into sentences so barge-in stops at a sentence boundary.
        """
        self._load_tts()
        self._interrupt.clear()

        # Split into sentences for finer-grained interruption
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text.strip()) or [text]

        # Start VAD barge-in listener in background
        barge_in_thread = threading.Thread(target=self._barge_in_listener, daemon=True)
        barge_in_thread.start()

        spoken_chars = 0
        for sentence in sentences:
            if self._interrupt.is_set():
                # Save interruption state
                self.cache.save_interruption(self.session, text, spoken_chars)
                logger.info("Barge-in at char %d", spoken_chars)
                break

            try:
                samples, sample_rate = self._tts.create(
                    sentence,
                    voice=self._tts_voice,
                    speed=self._tts_speed,
                    lang="en-us",
                )
                sd.play(samples, sample_rate)
                # Poll for barge-in while playing
                while sd.get_stream().active:
                    if self._interrupt.is_set():
                        sd.stop()
                        break
                    time.sleep(0.05)
                sd.wait()
                spoken_chars += len(sentence)
            except Exception as e:
                logger.warning("TTS failed for sentence (%s)", e)
                break

    def _barge_in_listener(self):
        """
        Runs in a background thread while TTS is playing.
        Detects voice activity and sets _interrupt if speech is heard.
        Uses silero-VAD if available, otherwise energy threshold fallback.
        """
        try:
            self._load_vad()
            use_silero = self._vad_model is not None
        except Exception:
            use_silero = False

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_FRAMES,
        ) as mic:
            while not self._interrupt.is_set():
                block, _ = mic.read(BLOCK_FRAMES)
                audio_chunk = block[:, 0]

                if use_silero:
                    tensor = self._np_to_tensor(audio_chunk)
                    prob = self._vad_model(tensor, SAMPLE_RATE).item()
                    if prob > self._vad_thresh:
                        self._interrupt.set()
                else:
                    # Energy fallback
                    rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
                    if rms > 0.02:
                        self._interrupt.set()

    # ------------------------------------------------------------------
    # VAD
    # ------------------------------------------------------------------

    def _load_vad(self):
        if self._vad_model is None:
            try:
                import torch
                model, utils = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    onnx=False,
                    verbose=False,
                )
                self._vad_model = model
                self._vad_utils = utils
            except Exception as e:
                logger.warning("silero-vad not available (%s); using energy VAD", e)
                self._vad_model = None

    @staticmethod
    def _np_to_tensor(audio: np.ndarray):
        import torch
        return torch.from_numpy(audio).float()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _record_until_silence(self) -> Optional[np.ndarray]:
        """
        Record from mic until 1.2 s of silence detected (VAD) or MAX_RECORD_S hit.
        Returns audio as float32 numpy array, or None on error.
        """
        try:
            self._load_vad()
        except Exception:
            pass

        recorded = []
        silence_blocks = 0
        silence_limit  = int(1.2 * SAMPLE_RATE / BLOCK_FRAMES)  # ~1.2 s silence
        started        = False
        deadline       = time.time() + MAX_RECORD_S

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=BLOCK_FRAMES,
            ) as mic:
                while time.time() < deadline:
                    block, _ = mic.read(BLOCK_FRAMES)
                    chunk = block[:, 0]

                    is_speech = self._is_speech(chunk)

                    if is_speech:
                        started = True
                        silence_blocks = 0
                        recorded.append(chunk.copy())
                    elif started:
                        recorded.append(chunk.copy())
                        silence_blocks += 1
                        if silence_blocks >= silence_limit:
                            break
        except Exception as e:
            logger.error("Recording error: %s", e)
            return None

        if not recorded:
            return None
        return np.concatenate(recorded)

    def _is_speech(self, chunk: np.ndarray) -> bool:
        if self._vad_model is not None:
            try:
                t = self._np_to_tensor(chunk)
                prob = self._vad_model(t, SAMPLE_RATE).item()
                return prob > self._vad_thresh
            except Exception:
                pass
        return float(np.sqrt(np.mean(chunk ** 2))) > 0.015
