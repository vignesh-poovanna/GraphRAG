# IP-SAKTI Sahayak — Daily Startup & Shutdown Guide

Use this guide whenever you turn on your machine or want to resume working with IP-SAKTI Sahayak.

---

## Startup Sequence (4 Steps)

### 1. Launch Docker Desktop
1. Open **Docker Desktop** from your Windows Start Menu.
2. Wait until the status in the lower-left corner shows **Engine running** (green).
3. The containers (`graphrag_neo4j` and `graphrag_qdrant`) are configured with `restart: unless-stopped`, so they will usually start automatically.
4. If they are stopped, run in PowerShell:
   ```powershell
   cd C:\Users\vigne\OneDrive\Desktop\GraphRAG
   docker compose up -d
   ```

---

### 2. Start the Backend API (Terminal 1)
Open a PowerShell terminal and run:

```powershell
cd C:\Users\vigne\OneDrive\Desktop\GraphRAG
.\venv\Scripts\Activate.ps1
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

Look for the confirmation lines:
```text
INFO: API ready
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```
> Keep this terminal open while you use the application.

---

### 3. Start ngrok for WhatsApp (Terminal 2)
Open a second PowerShell terminal and run:

```powershell
ngrok http 8000
```

You will see:
```text
Session Status                online
Forwarding                    https://mural-rentable-outlast.ngrok-free.dev -> http://localhost:8000
```
> Keep this terminal open.  
> Note: `mural-rentable-outlast.ngrok-free.dev` is your permanent domain, so you **do not** need to re-enter anything in Twilio.

---

### 4. Access the Application

#### A. Web Browser Interface
Open your browser and visit:
👉 **[http://localhost:8000/](http://localhost:8000/)**
- Chat with IP-SAKTI via text.
- Use speech queries.
- Click the green **WhatsApp** button in the navigation bar to display the QR code for others.

#### B. WhatsApp Mobile Interface
- Open WhatsApp on your phone.
- Go to the conversation with **`+1 415 523 8886`**.
- Send any Ayurveda IP or regulatory question!
- *(If 72 hours of inactivity have elapsed, send `join bar-greatly` once to reactivate the sandbox).*

---

## Verification Checklist

| Service | Port / URL | How to verify |
|---|---|---|
| **FastAPI Backend** | `http://localhost:8000/health` | Returns `{"status": "ok"}` |
| **Frontend Web App** | `http://localhost:8000/` | Webpage loads with full theme |
| **Qdrant Vector DB** | `http://localhost:6333/dashboard` | Qdrant web dashboard loads |
| **Neo4j Graph DB** | `http://localhost:7474` | Neo4j browser login loads |
| **ngrok Tunnel** | `http://127.0.0.1:4040` | Web inspection console for WhatsApp |

---

## Clean Shutdown Procedure

When you are finished using the application:
1. In **Terminal 1** (uvicorn): Press `Ctrl + C`.
2. In **Terminal 2** (ngrok): Press `Ctrl + C`.
3. To stop database containers and save system memory:
   ```powershell
   docker compose stop
   ```
   *(Your documents, vector embeddings, citations, and conversation history remain safely stored in Docker volumes and `data/session_cache.db`).*
