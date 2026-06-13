# Aethelgard — AI-Powered Digital Legacy Vault

Preserve your digital legacy with Aethelgard. Store your memories securely behind a 90-day dead-man switch and deliver them to your loved ones when they need it most.

---

## Tech Stack

| Layer    | Technology                     |
|----------|--------------------------------|
| Frontend | Next.js 15, Tailwind CSS, shadcn/ui |
| Backend  | Python FastAPI, Uvicorn        |
| Database | AWS DynamoDB (`Aethelgard_Vault`) |

---

## Prerequisites

- Node.js 18+
- Python 3.11+
- AWS account with DynamoDB access (credentials via `~/.aws/credentials` or env vars)

---

## Frontend

```bash
# 1. Install dependencies
cd aethelgard
npm install

# 2. Copy env file
cp .env.example .env.local

# 3. Start dev server
npm run dev
# → http://localhost:3000
```

---

## Backend

```bash
# 1. Enter backend directory
cd aethelgard/backend

# 2. Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env file and fill in your AWS credentials
cp .env.example .env

# 5. Start the server
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

---

## AWS Credentials

The backend uses `boto3` for DynamoDB access. Configure credentials **one** of these ways:

```bash
# Option A — AWS CLI (recommended for local dev)
aws configure

# Option B — environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

> Never commit real credentials. The `.env` file is in `.gitignore`.

---

## Initialize DynamoDB

Once the backend is running, call the admin endpoint to create the table:

```bash
curl -X POST http://localhost:8000/admin/init-db
```

Response:
```json
{"created": true, "table_name": "Aethelgard_Vault"}
```

> ⚠ **Protect this endpoint before going to production.** See the TODO comment in `backend/app/main.py`.

---

## Test Backend

```bash
cd backend
pytest tests/ -v
```

Expected output:
```
tests/test_health.py::test_health_returns_200        PASSED
tests/test_health.py::test_health_response_schema    PASSED
tests/test_health.py::test_health_service_name       PASSED
tests/test_health.py::test_docs_available            PASSED
tests/test_health.py::test_openapi_json_available    PASSED
```

---

## Dead Man's Switch Lifecycle

```
ACTIVE
  │  (no check-in for 90 days)
  ▼
PENDING_RELEASE  ◀──── check-in resets to ACTIVE
  │  POST /admin/release/{email}  →  generates nominee token
  ▼
Nominee visits /release/{token}
  │  POST /release/{token}/approve
  ▼
RELEASED
```

| Status             | Meaning                                                          |
|--------------------|------------------------------------------------------------------|
| `ACTIVE`           | User is checking in regularly. Vault is locked.                  |
| `PENDING_RELEASE`  | 90-day window expired. Awaiting nominee confirmation.            |
| `RELEASED`         | Nominee has approved the release. Vault access flow starts.      |

A check-in always resets status to `ACTIVE`, even from `PENDING_RELEASE`.

The scan engine runs on demand via `GET /admin/deadman/scan`. In production, schedule it daily with **AWS EventBridge** → **Lambda** (see `backend/app/services/scheduler.py` for the wiring guide).

### Release Token Lifecycle

```
POST /admin/release/{email}
  → token created (status: PENDING, expires in 72 h)

GET /release/{token}
  → validate token (no state change)
  → returns: valid | expired | used | not_found

POST /release/{token}/approve
  → token marked USED (one-time)
  → user status → RELEASED
  → token expires naturally (status: EXPIRED after expiry)
```

Token expiry is configurable via `RELEASE_TOKEN_EXPIRY_HOURS` (default 72 h).

TODO (production): Email the nominee their approval link automatically when a release request is created.

---

## API Routes

| Method | Path                                  | Description                                         |
|--------|---------------------------------------|-----------------------------------------------------|
| GET    | `/health`                             | Health check                                        |
| POST   | `/admin/init-db`                      | Create DynamoDB table                               |
| GET    | `/admin/deadman/scan`                 | Run Dead Man's Switch scan (ACTIVE → PENDING_RELEASE)|
| GET    | `/admin/deadman/overdue`              | List overdue ACTIVE users                           |
| POST   | `/admin/release/{email}`              | Create nominee release token for a PENDING_RELEASE user |
| POST   | `/users`                              | Register a new vault                                |
| GET    | `/users/{email}`                      | Get user metadata                                   |
| POST   | `/users/{email}/check-in`             | Record a check-in (resets countdown)                |
| POST   | `/users/{email}/vault`                | Create encrypted vault entry                        |
| GET    | `/users/{email}/vault`                | List vault entries (metadata only)                  |
| GET    | `/users/{email}/vault/{entry_id}`     | Get and decrypt a single entry                      |
| DELETE | `/users/{email}/vault/{entry_id}`     | Delete a vault entry                                |
| GET    | `/release/{token}`                    | Validate nominee release token (no state change)    |
| POST   | `/release/{token}/approve`            | Approve release (PENDING_RELEASE → RELEASED)        |
| POST   | `/users/{email}/family-guide`         | Generate AI family guide (RELEASED only)            |
| GET    | `/users/{email}/family-guide/demo`    | Sample guide (no release gate, uses fallback)       |

---

## Encryption Design

### How vault data is encrypted

Vault entry `sensitive_data` and `notes` are encrypted with **AES-256-GCM** before being written to DynamoDB.  Plaintext is never stored.

Each call generates a fresh 12-byte random nonce, so identical plaintexts produce distinct ciphertexts.  The GCM authentication tag is appended to the ciphertext by the `cryptography` library and verified on decrypt; any tampering raises an `InvalidTag` exception.

### Stored payload format

```json
{
  "ciphertext": "<base64>",
  "nonce":      "<base64>",
  "algorithm":  "AES-256-GCM",
  "mode":       "local"
}
```

For KMS mode, `encrypted_data_key` and `kms_key_id` are added.

### Local mode (development)

`ENCRYPTION_MODE=local` (default).  A 256-bit per-user key is derived from `LOCAL_MASTER_KEY` + the user's email using **HKDF-SHA256**.  No AWS dependency; suitable for local development and single-instance deployments.

```
LOCAL_MASTER_KEY  ──HKDF(info=email)──▶  per-user AES-256 key  ──▶  AES-256-GCM
```

**Generating a secure master key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Warning:** Rotating `LOCAL_MASTER_KEY` makes all existing vault ciphertext permanently unreadable. Back it up securely.

### KMS mode (production — TODO)

Set `ENCRYPTION_MODE=kms` and `KMS_KEY_ID=<arn-or-alias>`.  The backend will call `kms:GenerateDataKey` to produce a fresh 256-bit data key per operation (standard envelope encryption pattern).  The KMS-encrypted data key is stored alongside the ciphertext.  See the TODO comments in `backend/app/security/encryption.py` for the implementation guide.

### No plaintext storage guarantee

- `sensitive_data` and `notes` are encrypted before any DynamoDB call.
- The list endpoint (`GET /users/{email}/vault`) returns only metadata (title, entry_type, timestamps).
- `LOCAL_MASTER_KEY` is read from the environment and never logged or persisted by the application.

---

## DynamoDB Table Design

Table: `Aethelgard_Vault`  (single-table design)

| PK              | SK                | Item type           |
|-----------------|-------------------|---------------------|
| `USER#<email>`  | `METADATA`        | User record         |
| `USER#<email>`  | `VAULT#<uuid>`    | Encrypted vault entry |

---

## Family Guide

Once a vault reaches `RELEASED` status, any caller with the owner's email
can request an AI-generated family guide:

```
POST /users/{email}/family-guide
```

```
Encrypted Vault
      ↓
  Decrypt (AES-256-GCM)
      ↓
  Build context (group by entry type)
      ↓
  Gemini 1.5 Flash  ──(fails or no key)──▶  Deterministic fallback
      ↓
  Readable Family Guide
```

The guide covers:
- Introduction
- Important Accounts (credentials)
- Financial Assets
- Documents
- Digital Assets
- Personal Messages
- Instructions & wishes
- Closing message

**Fallback mode**: when `GEMINI_API_KEY` is not configured or the API is
unreachable, a deterministic structured guide is generated automatically.
No AI dependency required — the system always returns a result.

```bash
# Preview format without a real vault (no release gate)
curl http://localhost:8000/users/you@example.com/family-guide/demo
```

## Production Readiness Checklist

> **This application is not production-ready out of the box.**
> The following items must be addressed before handling real user data.

| # | Blocker | Detail |
|---|---------|--------|
| 1 | **Authentication required** | Every user route (`/users/*`, `/vault/*`, `/release/*`) is currently unprotected. Add JWT or AWS Cognito before exposing to the internet. Without auth, any caller who knows an email address can read or delete vault entries. |
| 2 | **Admin endpoints must be secured** | `/admin/*` and `/demo/*` routes have no access control. Protect them with an admin secret header (`X-Admin-Secret`) or remove them entirely before deploying. |
| 3 | **Replace LOCAL_MASTER_KEY with AWS KMS** | The local encryption mode (`ENCRYPTION_MODE=local`) is suitable only for development. In production, set `ENCRYPTION_MODE=kms` and `KMS_KEY_ID` so data keys are generated and protected by AWS KMS. Rotating `LOCAL_MASTER_KEY` makes all existing vault data permanently unreadable — plan a migration before rotating. |
| 4 | **Email delivery required** | The Dead Man's Switch creates a release token but does not contact the nominee. Integrate AWS SES or SendGrid to email the nominee their approval link when `create_release_request()` fires. Without this, nominees will never know to act. |
| 5 | **Legal review before storing estate documents** | Storing wills, beneficiary designations, and estate instructions may trigger legal obligations depending on your jurisdiction (data protection law, legal professional privilege, fiduciary duties). Consult a qualified lawyer before allowing users to store or distribute legal documents. |
| 6 | **HTTPS and CORS hardening** | The backend CORS policy currently allows `localhost`. Restrict `allow_origins` to your production domain and enforce HTTPS at the load balancer or reverse proxy. |
| 7 | **Atomic release transition** | `approve_release()` performs two sequential DynamoDB writes (mark token USED, then mark user RELEASED). A crash between them leaves the token consumed but the vault unreleased. Wrap both writes in a `TransactWriteItems` call before production. |
| 8 | **Audit all TODOs** | Run the command below to see every outstanding hardening item in the codebase. |

```bash
grep -rn "TODO (before production)" backend/
```

---

## Roadmap

- [ ] Authentication (JWT / AWS Cognito)
- [x] AES-256-GCM vault encryption
- [x] Dead Man's Switch (90-day check-in engine)
- [x] Nominee release portal
- [x] Gemini AI family guide generation
- [ ] KMS envelope encryption (production hardening)
- [ ] Automated nominee email delivery (SES/SendGrid)
- [ ] Atomic release transitions (DynamoDB TransactWriteItems)
- [ ] File/media vault (S3)
- [ ] Nominee authentication (verify identity before release)
