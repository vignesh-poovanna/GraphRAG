"""
Configuration management for GraphRAG
"""

import os
from dotenv import load_dotenv
import yaml
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager that loads from .env, YAML, or code"""
    
    def __init__(self, config_path=None):
        """Initialize with optional config file path"""
        # Load environment variables
        load_dotenv()
        
        # Default configuration
        self.config = {
            "neo4j": {
                "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                "user": os.getenv("NEO4J_USER", "neo4j"),
                "password": os.getenv("NEO4J_PASSWORD", "password")
            },
            "qdrant": {
                "host": os.getenv("QDRANT_HOST", "localhost"),
                "port": int(os.getenv("QDRANT_PORT", 6333)),
                "collection": os.getenv("QDRANT_COLLECTION", "document_chunks")
            },
            "embedding": {
                # Phase 3: multilingual-e5-large for cross-lingual retrieval (1024-dim)
                "model_name": os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large"),
                "dimension": int(os.getenv("EMBEDDING_DIMENSION", 1024)),
                "device": os.getenv("EMBEDDING_DEVICE", "cpu"),
                "max_length": int(os.getenv("EMBEDDING_MAX_LENGTH", 512)),
                # Legacy alias kept for qdrant_manager compat
                "vector_size": int(os.getenv("EMBEDDING_DIMENSION", 1024)),
            },
            "chunking": {
                "chunk_size": int(os.getenv("CHUNK_SIZE", 600)),
                "chunk_overlap": int(os.getenv("CHUNK_OVERLAP", 100)),
                "strategy": os.getenv("CHUNKING_STRATEGY", "structure_aware"),
                "max_chunk_size": int(os.getenv("MAX_CHUNK_SIZE", 1000)),
                "keep_tables_atomic": os.getenv("KEEP_TABLES_ATOMIC", "true").lower() == "true",
            },
            # Phase 7: EXTRACTION_LLM (local Ollama) vs SYNTHESIS_LLM (Groq)
            "llm": {
                "extraction_model": os.getenv("EXTRACTION_LLM", "llama3.2:3b"),
                "synthesis_model": os.getenv("SYNTHESIS_LLM", "llama-3.1-8b-instant"),
                "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                "synthesis_api_key": os.getenv("SYNTHESIS_LLM_API_KEY", ""),
                "synthesis_base_url": os.getenv("SYNTHESIS_LLM_BASE_URL", "https://api.groq.com/openai/v1"),
                # Cerebras: fast query classification (experimental)
                "classification_model": os.getenv("CEREBRAS_MODEL", "llama3.1-8b"),
                "classification_api_key": os.getenv("CEREBRAS_API_KEY", ""),
                "classification_base_url": os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
            },
            "language": {
                "detect": os.getenv("LANGUAGE_DETECT", "true").lower() == "true",
            },
            # Phase 8: Speech pipeline
            "speech": {
                "stt_model": os.getenv("SPEECH_STT_MODEL", "base"),
                "stt_device": os.getenv("SPEECH_STT_DEVICE", "cpu"),
                "tts_voice": os.getenv("SPEECH_TTS_VOICE", "af_heart"),
                "tts_speed": float(os.getenv("SPEECH_TTS_SPEED", "1.0")),
                "vad_threshold": float(os.getenv("SPEECH_VAD_THRESHOLD", "0.5")),
                "session_cache": os.getenv("SPEECH_SESSION_CACHE", "./data/session_cache.db"),
            },
        }
        
        # Override with YAML config if provided and is a YAML file
        if config_path and os.path.exists(config_path) and config_path.lower().endswith(('.yaml', '.yml')):
            self._load_from_yaml(config_path)
            logger.info(f"Loaded configuration from {config_path}")
        else:
            logger.info("Using default configuration and environment variables")
    
    def _load_from_yaml(self, path):
        """Load configuration from YAML file"""
        try:
            with open(path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    # Recursively update config
                    self._update_dict(self.config, yaml_config)
                    logger.debug(f"Loaded YAML configuration: {yaml_config}")
        except Exception as e:
            logger.error(f"Error loading YAML configuration: {str(e)}")
    
    def _update_dict(self, d, u):
        """Recursively update nested dictionary"""
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._update_dict(d.get(k, {}), v)
            else:
                d[k] = v
        return d
    
    def get(self, key, default=None):
        """Get a config value, traversing nested dictionaries with dot notation"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
        
    def set(self, key, value):
        """Set a config value, creating nested dictionaries as needed"""
        keys = key.split('.')
        d = self.config
        
        # Navigate to the right level
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            elif not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
            
        # Set the value
        d[keys[-1]] = value
    
    def __str__(self):
        """Return a string representation of the configuration"""
        return yaml.dump(self.config, default_flow_style=False)

# Create default configuration instance
config = Config()

# Export commonly used variables
NEO4J_URI = config.get('neo4j.uri')
NEO4J_USER = config.get('neo4j.user')
NEO4J_PASSWORD = config.get('neo4j.password')

QDRANT_HOST = config.get('qdrant.host')
QDRANT_PORT = config.get('qdrant.port')
QDRANT_COLLECTION = config.get('qdrant.collection')

EMBEDDING_MODEL = config.get('embedding.model_name')
EMBEDDING_DIMENSION = config.get('embedding.dimension')

EXTRACTION_LLM = config.get('llm.extraction_model')
SYNTHESIS_LLM = config.get('llm.synthesis_model')

CHUNKING_STRATEGY = config.get('chunking.strategy')
MAX_CHUNK_SIZE = config.get('chunking.max_chunk_size')
KEEP_TABLES_ATOMIC = config.get('chunking.keep_tables_atomic')