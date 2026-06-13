# Aethelgard — AWS Production Deployment Guide

Target stack: Railway (FastAPI backend) + Vercel (Next.js frontend) + AWS DynamoDB.

**Current encryption mode: `local` (HKDF + LOCAL_MASTER_KEY).**
KMS mode is stubbed but not implemented — the functions raise `NotImplementedError`.
Do not set `ENCRYPTION_MODE=kms` until `_generate_kms_data_key()` and
`_decrypt_kms_data_key()` in `backend/app/security/encryption.py` are completed.

---

## 1. Required AWS Resources Checklist

### Must have before first deploy

- [ ] **AWS account** with IAM access (root or admin-level to create IAM user + DynamoDB table)
- [ ] **IAM user** with programmatic access keys (for Railway backend to call DynamoDB)
  - Attach the inline policy in section 3 below — no managed policies needed
  - Store the Access Key ID and Secret Access Key; you will not see the secret again
- [ ] **DynamoDB table: `Aethelgard_Vault`**
  - Region: `us-east-1` (or match your `AWS_REGION` env var)
  - Billing mode: `PAY_PER_REQUEST` (no capacity planning needed)
  - Do not create GSIs yet — the current scan uses a filter expression (acceptable at this scale)
  - Create via AWS Console, CLI, or the `/admin/init-db` API endpoint after deploy

### Needed later (production hardening — not yet implemented)

- [ ] **AWS KMS Customer Master Key (CMK)** — symmetric, for vault envelope encryption
  - Only required when `ENCRYPTION_MODE=kms` is implemented
  - Note the full ARN (`arn:aws:kms:us-east-1:<account>:key/<key-id>`) for `KMS_KEY_ID`
  - Add `kms:GenerateDataKey` and `kms:Decrypt` to the IAM policy at that point
- [ ] **AWS Secrets Manager secret** for `LOCAL_MASTER_KEY`
  - Currently read from env var; moving it to Secrets Manager removes it from Railway's dashboard
  - Requires `secretsmanager:GetSecretValue` added to the IAM policy
- [ ] **AWS SES verified domain** — for nominee email delivery
  - Domain: the domain your nominee emails will be sent from
  - Requires SES out of sandbox mode (submit AWS support request for production sending)
  - Requires `ses:SendEmail` added to the IAM policy
- [ ] **EventBridge rule + Lambda** — for the daily Dead Man's Switch scan
  - See `backend/app/services/scheduler.py` — the Lambda handler is commented out and ready
  - Requires a separate Lambda execution role with `dynamodb:Scan`, `dynamodb:UpdateItem`,
    `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

---

## 2. DynamoDB Table Schema

### Table definition

| Property | Value |
|---|---|
| Table name | `Aethelgard_Vault` |
| Partition key (PK) | `PK` — String |
| Sort key (SK) | `SK` — String |
| Billing mode | `PAY_PER_REQUEST` |
| Encryption | AWS-owned key (default) — upgrade to CMK when KMS mode is implemented |

```bash
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

### Item type 1 — User metadata

**Key:** `PK = USER#<email>` / `SK = METADATA`

| Attribute | Type | Example | Notes |
|---|---|---|---|
| `PK` | S | `USER#alice@example.com` | Lowercase, stripped |
| `SK` | S | `METADATA` | Literal constant |
| `email` | S | `alice@example.com` | |
| `nominee_email` | S / null | `bob@example.com` | Optional |
| `created_at` | S | `2025-01-15T09:00:00+00:00` | UTC ISO-8601 |
| `updated_at` | S | `2025-06-13T14:22:00+00:00` | Updated on every write |
| `last_checkin_at` | S | `2025-06-01T08:00:00+00:00` | Reset by check-in |
| `next_check_due_at` | S | `2025-08-30T08:00:00+00:00` | `last_checkin_at + dead_man_switch_days` |
| `dead_man_switch_days` | N | `90` | Configurable per-user in future; currently global |
| `status` | S | `ACTIVE` | `ACTIVE` \| `PENDING_RELEASE` \| `RELEASED` |
| `release_candidate_at` | S / null | `2025-09-01T09:00:00+00:00` | Set when transitioned to PENDING_RELEASE |
| `released_at` | S / null | `2025-09-02T11:00:00+00:00` | Set when nominee approves release |

### Item type 2 — Encrypted vault entry

**Key:** `PK = USER#<email>` / `SK = VAULT#<uuid>`

| Attribute | Type | Example | Notes |
|---|---|---|---|
| `PK` | S | `USER#alice@example.com` | Same partition as METADATA |
| `SK` | S | `VAULT#3f2a1b...` | UUID v4 |
| `entry_id` | S | `3f2a1b...` | UUID without prefix |
| `entry_type` | S | `credentials` | `message` \| `note` \| `credentials` \| `document` |
| `title` | S | `Chase Checking Account` | Plaintext — not sensitive |
| `sensitive_data` | M | `{"ciphertext": "...", "nonce": "...", "algorithm": "AES-256-GCM", "mode": "local"}` | AES-256-GCM payload (see below) |
| `notes` | M / null | _(same format as sensitive_data)_ | Optional, also encrypted |
| `created_at` | S | `2025-06-13T10:00:00+00:00` | |
| `updated_at` | S | `2025-06-13T10:00:00+00:00` | |

**Encrypted payload format** (stored as a DynamoDB Map):

```json
{
  "ciphertext": "<base64>",
  "nonce":      "<base64(12 bytes)>",
  "algorithm":  "AES-256-GCM",
  "mode":       "local"
}
```

When KMS mode is implemented, two additional fields appear:
```json
{
  "encrypted_data_key": "<base64>",
  "kms_key_id":         "arn:aws:kms:us-east-1:<account>:key/<key-id>"
}
```

### Item type 3 — Release token

**Key:** `PK = RELEASE#<token>` / `SK = REQUEST`

| Attribute | Type | Example | Notes |
|---|---|---|---|
| `PK` | S | `RELEASE#abc123...` | 256-bit URL-safe token |
| `SK` | S | `REQUEST` | Literal constant |
| `token` | S | `abc123...` | Same as token portion of PK |
| `owner_email` | S | `alice@example.com` | Vault owner |
| `nominee_email` | S / null | `bob@example.com` | Recipient of the release link |
| `created_at` | S | `2025-09-01T09:00:00+00:00` | |
| `expires_at` | S | `2025-09-04T09:00:00+00:00` | `created_at + RELEASE_TOKEN_EXPIRY_HOURS` |
| `status` | S | `PENDING` | `PENDING` \| `USED` \| `EXPIRED` |
| `used_at` | S / null | `2025-09-02T11:00:00+00:00` | Set on nominee approval |

---

## 3. Railway Environment Variables

Set these in the Railway project dashboard → Variables.

**Start command** (set in Railway service settings):
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Root directory** (set in Railway service settings): `backend`

### Required

| Variable | Value | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Disables dev guards |
| `AWS_REGION` | `us-east-1` | Match the region where the table was created |
| `AWS_ACCESS_KEY_ID` | `AKIA...` | From the IAM user created in section 1 |
| `AWS_SECRET_ACCESS_KEY` | `...` | From the IAM user — treat as a password |
| `DYNAMODB_TABLE_NAME` | `Aethelgard_Vault` | Must match the table name exactly |
| `ENCRYPTION_MODE` | `local` | Do not change to `kms` until the KMS functions are implemented |
| `LOCAL_MASTER_KEY` | 64-char hex string | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` — **never rotate after first user is created** |

### Optional — set for production use

| Variable | Value | Notes |
|---|---|---|
| `APP_NAME` | `Aethelgard API` | Appears in `/health` and API docs |
| `DEAD_MAN_SWITCH_DAYS` | `90` | Default: 90. Affects all new check-in calculations |
| `RELEASE_TOKEN_EXPIRY_HOURS` | `72` | Default: 72. Nominee link lifetime in hours |
| `GEMINI_API_KEY` | `AIza...` | Optional. If unset, the deterministic fallback guide is used |

### Leave blank / do not set

| Variable | Notes |
|---|---|
| `DYNAMODB_ENDPOINT_URL` | Must be empty for real AWS. Only used for local moto server |
| `KMS_KEY_ID` | Leave unset until KMS encryption is implemented |

### IAM inline policy for the Railway IAM user

Attach this as an inline policy on the IAM user. Replace `<region>` and `<account-id>`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBTableAccess",
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
      "Resource": "arn:aws:dynamodb:<region>:<account-id>:table/Aethelgard_Vault"
    }
  ]
}
```

`dynamodb:CreateTable` can be removed after `/admin/init-db` has been called once and the table exists. `dynamodb:Scan` is used by the Dead Man's Switch engine and by `delete_all_user_items` (demo reset).

---

## 4. Vercel Environment Variables

Set these in Vercel → Project Settings → Environment Variables.

| Variable | Scope | Value |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Production, Preview | `https://<your-railway-app>.up.railway.app` |

**No other environment variables are needed.** The frontend is a pure client — it makes fetch calls to the backend URL above. All secrets live on Railway.

For Preview deployments targeting a staging backend, create a second Railway service and set a separate `NEXT_PUBLIC_API_BASE_URL` scoped to Preview only.

---

## 5. Deployment Verification Steps

Run these in order after deploying. Replace `$API` and `$FRONTEND` with your actual URLs.

```bash
API=https://your-app.up.railway.app
FRONTEND=https://your-app.vercel.app
```

### Step 1 — Backend health

```bash
curl -s "$API/health" | python3 -m json.tool
```
Expected:
```json
{
  "status": "ok",
  "service": "Aethelgard API",
  "environment": "production"
}
```
**Fails → Railway service is not running. Check Railway deploy logs.**

### Step 2 — Create the DynamoDB table

```bash
curl -s -X POST "$API/admin/init-db" | python3 -m json.tool
```
Expected (first run):
```json
{ "created": true, "table_name": "Aethelgard_Vault" }
```
Expected (subsequent runs):
```json
{ "created": false, "table_name": "Aethelgard_Vault" }
```
**Fails with connection error → check AWS credentials and region in Railway env vars.**
**Fails with 500 → check CloudWatch/Railway logs for `NoCredentialsError` or `AccessDeniedException`.**

### Step 3 — Encryption is working

```bash
curl -s -X POST "$API/users" \
  -H "Content-Type: application/json" \
  -d '{"email": "verify-test@aethelgard.ai", "nominee_email": "nominee@aethelgard.ai"}' \
  | python3 -m json.tool
```
Expected: a `UserMetadata` object with `"status": "ACTIVE"` and timestamps.

**Fails with 500 + `LOCAL_MASTER_KEY is not set` → set `LOCAL_MASTER_KEY` in Railway.**
**Fails with 500 + `NotImplementedError` → `ENCRYPTION_MODE` is set to `kms`; change it to `local`.**

### Step 4 — DynamoDB read/write round-trip

```bash
curl -s "$API/users/verify-test%40aethelgard.ai" | python3 -m json.tool
```
Expected: same `UserMetadata` object.

```bash
curl -s -X POST "$API/users/verify-test%40aethelgard.ai/check-in" | python3 -m json.tool
```
Expected: `CheckInResponse` with updated `last_checkin_at` and `next_check_due`.

### Step 5 — Clean up the test user

The test user must be removed manually since there is no delete-user endpoint. Use the AWS Console or CLI:

```bash
aws dynamodb delete-item \
  --table-name Aethelgard_Vault \
  --key '{"PK": {"S": "USER#verify-test@aethelgard.ai"}, "SK": {"S": "METADATA"}}' \
  --region us-east-1
```

### Step 6 — Frontend loads and connects to backend

```bash
curl -o /dev/null -s -w "%{http_code}" "$FRONTEND"
```
Expected: `200`

Open `$FRONTEND` in a browser. Open DevTools → Network. Register a test email. The `POST /users` request should show status 201 and the response body should contain `"status": "ACTIVE"`.

### Step 7 — Demo endpoint is accessible (expected in this deployment)

```bash
curl -o /dev/null -s -w "%{http_code}" "$API/demo/setup" -X POST
```
Expected: `200`

**Before accepting real users:** protect `/demo/*` and `/admin/*` with an `X-Admin-Secret` header
check or remove them from the deployed API. These endpoints reset demo data and bypass business
logic — they must not be reachable by the public.

---

## Production Blockers Summary

These must be resolved before the app handles real user data:

| # | Blocker | Where to fix |
|---|---|---|
| 1 | No authentication on any route | Add JWT / Cognito middleware to all `/users/*`, `/vault/*`, `/release/*` routes |
| 2 | Admin and demo routes are public | Add `X-Admin-Secret` header guard to `/admin/*`; remove or protect `/demo/*` |
| 3 | KMS encryption not implemented | Complete `_generate_kms_data_key()` and `_decrypt_kms_data_key()` in `encryption.py` |
| 4 | Nominee email not sent | Integrate SES or SendGrid in `backend/app/services/nominee.py:create_release_request()` |
| 5 | Release transition is not atomic | Wrap the two DynamoDB writes in `approve_release()` with `TransactWriteItems` |
| 6 | Dead Man's Switch requires manual trigger | Deploy `scheduler.py` Lambda + EventBridge daily cron |
| 7 | CORS allows localhost origins | Change `allow_origins` in `main.py` to `["https://yourdomain.com"]` |
