# Aethelgard — Deployment Checklist

This guide covers deploying Aethelgard to production. Work through sections in order.

---

## Prerequisites

- [ ] AWS account with IAM access
- [ ] Domain name (for frontend and API)
- [ ] Node.js 18+ and Python 3.11+ on your build machine
- [ ] AWS CLI configured (`aws configure`)

---

## 1. DynamoDB Setup

### Create the table

```bash
# Option A — via the admin API (easiest for first deploy)
curl -X POST https://your-api-domain.com/admin/init-db

# Option B — directly via AWS CLI
aws dynamodb create-table \
  --table-name Aethelgard_Vault \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### IAM permissions required

Your backend execution role needs these DynamoDB permissions on `arn:aws:dynamodb:<region>:<account>:table/Aethelgard_Vault`:

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:CreateTable",
    "dynamodb:DescribeTable",
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:BatchWriteItem"
  ],
  "Resource": "arn:aws:dynamodb:*:*:table/Aethelgard_Vault"
}
```

---

## 2. Backend Deployment

### Option A — AWS Lambda + API Gateway (recommended)

1. **Package the app**

   ```bash
   cd backend
   pip install -r requirements.txt -t ./package
   cp -r app ./package/
   ```

2. **Create the Lambda function**

   - Runtime: Python 3.12
   - Handler: `app.main.handler` (add Mangum adapter — see below)
   - Memory: 512 MB
   - Timeout: 30 s

3. **Add Mangum adapter** (ASGI → Lambda)

   ```bash
   pip install mangum
   ```

   In `backend/app/main.py`, append:

   ```python
   from mangum import Mangum
   handler = Mangum(app)
   ```

4. **Set environment variables** on the Lambda function (see Environment Variables section below)

5. **Create API Gateway** — HTTP API, proxy all routes to Lambda

6. **Protect admin routes** — Add `X-Admin-Secret` header check to `/admin/*` before deploying

### Option B — EC2 / container (simpler)

```bash
# On your server
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.production.example .env
# → Fill in all values in .env

# Run with gunicorn behind nginx
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Configure nginx to proxy `api.yourdomain.com` → `localhost:8000` with HTTPS via Let's Encrypt.

### Option C — Railway / Render (fastest)

1. Push `backend/` as a standalone repo
2. Set all environment variables in the platform dashboard
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## 3. Frontend Deployment

### Vercel (recommended)

1. **Import the project**

   ```bash
   cd aethelgard   # project root (not backend/)
   npx vercel
   ```

   Or connect via the Vercel dashboard: Import Git Repository → select `aethelgard`.

2. **Set environment variables** in Vercel dashboard → Project Settings → Environment Variables:

   | Variable | Value |
   |----------|-------|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://api.yourdomain.com` |

3. **Verify the build** — Vercel runs `next build` automatically. Confirm all 6 routes compile.

4. **Configure domain** — Add your custom domain in Vercel project settings.

5. **Confirm `/demo` is a 404** — Visit `https://yourdomain.com/demo` in production. It must return a 404 (the `notFound()` server guard handles this automatically).

### Other platforms (Netlify, Cloudflare Pages)

```bash
# Build locally
npm run build

# Output is in .next/ — deploy as a Next.js app (not static export)
# Both Netlify and Cloudflare support Next.js SSR via their adapters.
```

---

## 4. Environment Variables

### Backend (set in Lambda env, EC2 `.env`, or platform dashboard)

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `APP_NAME` | Yes | `Aethelgard API` | |
| `ENVIRONMENT` | Yes | `production` | |
| `AWS_REGION` | Yes | `us-east-1` | |
| `DYNAMODB_TABLE_NAME` | Yes | `Aethelgard_Vault` | |
| `ENCRYPTION_MODE` | Yes | `kms` | Use `local` only for dev |
| `KMS_KEY_ID` | Yes (kms mode) | `arn:aws:kms:...` | **Blocker — KMS not yet implemented** |
| `LOCAL_MASTER_KEY` | Yes (local mode) | 64-char hex | Dev only. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GEMINI_API_KEY` | No | `AIza...` | Fallback guide used if unset |
| `DEAD_MAN_SWITCH_DAYS` | No | `90` | Default: 90 |
| `RELEASE_TOKEN_EXPIRY_HOURS` | No | `72` | Default: 72 |
| `DYNAMODB_ENDPOINT_URL` | No | _(blank)_ | Leave blank for AWS; `http://localhost:8001` for local DynamoDB |

Use `.env.production.example` at the project root as a reference template.

### Frontend (set in Vercel or `.env.local`)

| Variable | Required | Example |
|----------|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | `https://api.yourdomain.com` |

---

## 5. Dead Man's Switch — Production Scheduling

The Dead Man's Switch scan currently runs on demand via `GET /admin/deadman/scan`. For production:

1. **Create a Lambda** wrapping `run_deadman_scan()` (see `backend/app/services/scheduler.py` — the handler is commented out and ready to uncomment)

2. **Create an EventBridge rule**

   ```bash
   aws events put-rule \
     --name AethelgardDMSScan \
     --schedule-expression "cron(0 9 * * ? *)" \
     --state ENABLED

   aws events put-targets \
     --rule AethelgardDMSScan \
     --targets Id=1,Arn=<lambda-arn>
   ```

3. **IAM** — grant the scheduler role `lambda:InvokeFunction` on the Lambda ARN

---

## 6. CORS Configuration

Before going live, restrict CORS in `backend/app/main.py`:

```python
# Current (development)
allow_origins=["*"]

# Production
allow_origins=["https://yourdomain.com"]
```

---

## 7. Production Blockers (must resolve before launch)

These are hard blockers — do not expose to real users until resolved.

- [ ] **Authentication** — All `/users/*`, `/vault/*`, `/release/*` routes are unprotected. Add JWT or AWS Cognito middleware.
- [ ] **Admin/demo route protection** — Add `X-Admin-Secret` header check or remove `/admin/*` and `/demo/*` from the deployed API.
- [ ] **KMS encryption** — Implement `_generate_kms_data_key()` and `_decrypt_kms_data_key()` in `backend/app/security/encryption.py` before storing real vault data.
- [ ] **Nominee email** — Integrate SES or SendGrid in `create_release_request()` so nominees are notified automatically.
- [ ] **Atomic release** — Wrap the two DynamoDB writes in `approve_release()` with `TransactWriteItems` to prevent partial state on crash.
- [ ] **Legal review** — Complete jurisdiction review before accepting real estate documents or wills.
- [ ] **HTTPS enforcement** — Enforce HTTPS at load balancer or reverse proxy; restrict CORS to production domain.

---

## 8. Smoke Test After Deploy

Run these checks after deploying to confirm the stack is healthy:

```bash
# Health
curl https://api.yourdomain.com/health
# Expected: {"service": "Aethelgard API", "status": "ok"}

# API docs accessible
curl -o /dev/null -s -w "%{http_code}" https://api.yourdomain.com/docs
# Expected: 200

# Frontend loads
curl -o /dev/null -s -w "%{http_code}" https://yourdomain.com
# Expected: 200

# /demo is a 404 in production
curl -o /dev/null -s -w "%{http_code}" https://yourdomain.com/demo
# Expected: 404
```
