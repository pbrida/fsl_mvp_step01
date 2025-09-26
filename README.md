# Fantasy Stock League — Step 1 (API Starter)

This starter gives you a **FastAPI** project you can run in VS Code. We'll expand it step-by-step.

## What you’ll have after this step
- A running API server (`/health` endpoint)
- SQLite database file (`dev.db`) created automatically
- Hot reload during development

## Prereqs
- Python 3.10 or newer
- VS Code
- Git (optional for now)

## 1) Open in VS Code
- Unzip this folder somewhere (e.g., `Documents/fsl-mvp`).
- Open the folder in VS Code (`File → Open Folder...`).

## 2) Create & activate a virtual environment
### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3) Install dependencies
```bash
pip install -r requirements.txt
```

## 4) Run the server (hot reload)
```bash
uvicorn fantasy_stocks.main:app --reload
```
Visit: http://127.0.0.1:8000/health  (should return `{"status":"ok"}`)  
Docs (auto): http://127.0.0.1:8000/docs

## 5) Next steps (coming in Step 2)
- Add database models for leagues, users, rosters
- Add endpoints for creating a league
- Add a simple in-memory "draft room"
