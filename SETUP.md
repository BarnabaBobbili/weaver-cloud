# Weaver — Setup Guide

## Prerequisites
- Python 3.11+
- Node.js 20+
- A Supabase project (free tier works)

---

## Step 1: Supabase Configuration

1. Go to your [Supabase project](https://supabase.com) → **Settings → Database → Connection String**
2. Copy the **Transaction Pooler** URL (port 6543) — used for API traffic
3. Copy the **Direct Connection** URL (port 5432) — used for migrations

---

## Step 2: Backend Setup

```powershell
cd "E:\MTech\MTech Sem2\Cyber Security\Project\Weaver\backend"

# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env from template
copy .env.example .env
```

Edit `.env` and fill in:
| Key | Value |
|---|---|
| `DATABASE_URL` | Supabase Transaction Pooler URL (port 6543) |
| `DATABASE_URL_DIRECT` | Supabase Direct connection URL (port 5432) |
| `JWT_SECRET_KEY` | Run: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MFA_ENCRYPTION_KEY` | Run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATA_ENCRYPTION_KEK` | Run: `python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"` |

```powershell
# 4. Create tables + seed default admin + 4 crypto policies
python scripts/seed_db.py

# 5. Generate ML training dataset
python scripts/generate_dataset.py

# 6. Train the sensitivity classifier (~1-2 minutes)
python -m app.ml.train
```

> **Default admin credentials:** `admin@weaver.local` / `Admin@1234`  
> ⚠️ Change the password after first login!

```powershell
# 7. Start the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

---

## Step 3: Frontend Setup

```powershell
cd "E:\MTech\MTech Sem2\Cyber Security\Project\Weaver\frontend"

npm install
npm run dev
```

Open: [http://localhost:5173](http://localhost:5173)

The Vite dev server proxies all `/api` requests to `http://localhost:8000` automatically.

---

## Step 4: Run Tests

```powershell
cd "E:\MTech\MTech Sem2\Cyber Security\Project\Weaver\backend"
venv\Scripts\activate

# Set test DB URL (can reuse dev DB)
$env:TEST_DATABASE_URL = "your-supabase-url-here"

# Run all tests
pytest tests/ -v --tb=short

# Security static analysis
pip install bandit
bandit -r app/ -f text
```

---

## Step 5: Security Scanning

```powershell
# Verify server is running on localhost:8000

# 1. Nmap
nmap -sV -sC -p- localhost -oN security_reports/nmap_scan.txt

# 2. Nikto
nikto -h http://localhost:8000 -o security_reports/nikto_report.txt

# 3. Bandit (Python static analysis)
bandit -r app/ -f json -o ../security_reports/bandit_report.json

# 4. OWASP ZAP (Docker)
docker run -t owasp/zap2docker-stable zap-full-scan.py -t http://host.docker.internal:8000 -r zap_report.html
```

---

## Architecture Summary

```
classify text/file
    → Layer 1: PII regex (SSN, credit card, Aadhaar...)
    → Layer 2: ML Random Forest (TF-IDF + PII features)
    → Layer 3: max(pii_level, ml_level) decision
    → LIME explanation (top 6 features + weights)
    → CryptoPolicy lookup
    → AES-GCM encrypt (DEK/KEK model)
    → Share link (hashed token, never stored raw)
    → Public decrypt URL
```

| Sensitivity | Encryption | KDF | Signing | MFA |
|---|---|---|---|---|
| Public | None (Base64) | — | — | No |
| Internal | AES-128-GCM | PBKDF2-SHA256 310K | — | No |
| Confidential | AES-256-GCM | PBKDF2-SHA256 600K | ECDSA-P256 | No |
| Highly Sensitive | AES-256-GCM | PBKDF2-SHA512 600K | RSA-PSS | **Yes** |
