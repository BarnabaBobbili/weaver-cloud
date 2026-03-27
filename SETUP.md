# Weaver Setup Guide

This guide covers both local development and Azure-connected execution.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL client tools (`psql`, `pg_dump`) for DB operations
- Azure CLI (`az`) for cloud tasks

## 1. Backend Setup (Local)

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\backend"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration Modes

- **Cloud-first mode (recommended for deployed env):**
  - Uses `KEY_VAULT_URL` + managed identity/client credentials.
  - Secrets are loaded from Azure Key Vault.
- **Direct DB mode (development/testing):**
  - Uses `DATABASE_URL` / `DATABASE_URL_DIRECT`.
  - Useful for local iteration and migration scripts.

Create `.env` only if your local workflow requires direct variables:

```powershell
copy .env.example .env
```

Then seed baseline data:

```powershell
python scripts/seed_db.py
```

Start backend:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 2. Frontend Setup (Local)

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\frontend"
npm install
npm run dev
```

Frontend dev URL: `http://localhost:5173`  
Backend API docs: `http://localhost:8000/api/docs`

## 3. Test Execution

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\backend"
venv\Scripts\activate
pytest tests -v --tb=short
```

## 4. Optional: Dataset + Model Training

```powershell
cd "E:\MTech\MTech Sem2\Cloud\Project\Weaver\backend"
python scripts/generate_dataset.py
python -m app.ml.train
```

## 5. Post-Setup Security Notes

- Change default seeded admin password immediately after first login.
- Do not commit secrets, tokens, registry passwords, or connection strings.
- Use Key Vault for production secrets; avoid long-term secret storage in `.env`.
