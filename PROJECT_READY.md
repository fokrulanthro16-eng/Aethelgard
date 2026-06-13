# Aethelgard — Project Ready

AI-Powered Digital Legacy Vault · Product Submission

---

## What It Does

Aethelgard automatically delivers your digital legacy to your loved ones when you're no longer around — without requiring any manual setup from your family.

1. **Vault** — Store bank accounts, insurance, wills, crypto wallets, personal messages. All encrypted with AES-256-GCM before leaving your device.
2. **Dead Man's Switch** — If you miss a 90-day check-in, the system detects inactivity and prepares your vault for release.
3. **Nominee Release** — A secure, one-time link is sent to your trusted nominee. They click "Approve" and the vault is released.
4. **AI Family Guide** — Gemini 1.5 Flash generates a readable, organised family guide from your encrypted entries. A deterministic fallback always works if Gemini is unavailable.

---

## Architecture Summary

```
Browser (Next.js 15 + React 19)
        │  HTTPS REST
        ▼
FastAPI Backend (Python 3.11 + Pydantic v2)
        │
        ├─ AES-256-GCM Encryption (HKDF-SHA256 per-user keys)
        │
        ├─ AWS DynamoDB (single-table design, 3 item types)
        │
        ├─ Dead Man's Switch Engine (90-day scan, EventBridge-ready)
        │
        ├─ Nominee Release Portal (256-bit token, 72h expiry, one-time)
        │
        └─ Gemini 1.5 Flash Guide Generator (fallback always available)
```

DynamoDB table items:

| PK | SK | Purpose |
|----|----|---------|
| `USER#<email>` | `METADATA` | User record + status |
| `USER#<email>` | `VAULT#<uuid>` | AES-256-GCM encrypted entry |
| `RELEASE#<token>` | `REQUEST` | Nominee release token |

---

## Validation Results

```
168 tests · 0 failures · 0 TypeScript errors · build: success

test_health.py        5 tests   — health check, docs routes
test_users.py        11 tests   — registration, login, check-in
test_encryption.py   18 tests   — AES-256-GCM round-trips, HKDF key derivation
test_vault.py        18 tests   — encrypted CRUD for vault entries
test_deadman.py      22 tests   — scan engine, status transitions
test_release.py      35 tests   — token lifecycle, approval, expiry
test_family_guide.py 31 tests   — Gemini path, fallback, release gate
test_demo.py         18 tests   — demo setup, idempotency, stats endpoint
```

Run all tests:

```bash
cd backend
pytest tests/ -v
```

---

## Deployment Commands

### Local Development

```bash
# Terminal 1 — Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
cp .env.example .env
# → Edit .env: set LOCAL_MASTER_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
npm install
npm run dev
```

Backend: http://localhost:8000
Frontend: http://localhost:3000
API docs: http://localhost:8000/docs

### Initialise DynamoDB Table

```bash
curl -X POST http://localhost:8000/admin/init-db
```

---

## Developer Tools (Dev Only)

```bash
# Load a complete demo scenario (5 encrypted entries, PENDING_RELEASE, release token)
curl -X POST http://localhost:8000/demo/setup

# View system capability stats
curl http://localhost:8000/demo/stats

# Run Dead Man's Switch scan
curl http://localhost:8000/admin/deadman/scan
```

The frontend developer tools panel is available at http://localhost:3000/demo (hidden in production builds).

---

## Product Pages

| URL | What it shows |
|-----|--------------|
| http://localhost:3000 | Product landing + vault app (family-focused, no demo UI) |
| http://localhost:3000/architecture | End-to-end system diagram |
| http://localhost:3000/judge | Live stats dashboard (test count, encryption, AI, DMS) |
| http://localhost:3000/release/{token} | Nominee approval portal |
| http://localhost:3000/demo | Developer tools — seed data, system stats (dev only) |
| http://localhost:8000/docs | Full OpenAPI docs for all 20 routes |

---

## Environment Variables

```env
# backend/.env

APP_NAME=Aethelgard API
ENVIRONMENT=development
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
DYNAMODB_TABLE_NAME=Aethelgard_Vault
DEAD_MAN_SWITCH_DAYS=90

# Required for vault encryption
ENCRYPTION_MODE=local
LOCAL_MASTER_KEY=<64-char hex — generate with: python -c "import secrets; print(secrets.token_hex(32))">

# Optional — AI guide generation (fallback used if not set)
GEMINI_API_KEY=

# Production hardening (not yet implemented — see README blockers)
# KMS_KEY_ID=
# ENCRYPTION_MODE=kms

# Optional
RELEASE_TOKEN_EXPIRY_HOURS=72
DYNAMODB_ENDPOINT_URL=
```

---

## Steps Completed

| Step | Feature | Status |
|------|---------|--------|
| 1 | FastAPI + DynamoDB integration, I AM OK check-in | ✓ |
| 1 audit | Dead function removal, unused imports, env file cleanup | ✓ |
| 2 | AES-256-GCM vault encryption with HKDF-SHA256 | ✓ |
| 3 | Dead Man's Switch engine (scan, ACTIVE → PENDING_RELEASE) | ✓ |
| 4 | Nominee Release Portal (token, approve, PENDING → RELEASED) | ✓ |
| 5 | Gemini AI Family Guide (with fallback, release gate) | ✓ |
| 6 | Demo tooling + architecture/judge pages | ✓ |
| 7 | Production-mode conversion (demo UI isolated, landing rewritten) | ✓ |

---

## Production Hardening (TODO stubs already in code)

- **Authentication**: JWT / AWS Cognito on all user routes
- **KMS encryption**: `kms:GenerateDataKey` envelope encryption replacing `LOCAL_MASTER_KEY`
- **SES/SendGrid**: Auto-email nominee when release request is created
- **EventBridge + Lambda**: Schedule Dead Man's Switch scan daily
- **TransactWriteItems**: Atomic `mark_release_used` + `mark_released`
- **GSI on SK=METADATA**: Avoid full-table scan in `scan_all_user_metadata`
- **Rate limiting**: Protect check-in endpoint
- **CORS hardening**: Restrict to production domain

See `DEPLOYMENT_CHECKLIST.md` for the full deployment guide.
