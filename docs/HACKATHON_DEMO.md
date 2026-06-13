# Aethelgard — Product Demo Script (3 minutes)

## The Problem (30 seconds)

Most people have:
- Bank accounts, crypto wallets, and insurance policies their family can't find
- Passwords stored only in their head
- No plan for what happens to their digital life

When someone dies unexpectedly, their family spends months — sometimes years — trying to locate accounts, fighting banks, missing insurance payouts. **The average estate loses $15,000 to unclaimed accounts.**

---

## The Solution (30 seconds)

**Aethelgard** is an AI-powered Digital Legacy Vault with an automatic Dead Man's Switch.

- Store everything your family needs: bank accounts, insurance, will location, crypto, emergency contacts
- All encrypted with AES-256-GCM before it ever leaves your browser
- A 90-day check-in system detects when you're gone — automatically
- Your trusted nominee receives a secure link to unlock your vault
- Gemini AI generates a readable family guide from your encrypted entries

**Zero reliance on manual processes. Zero stored plaintext.**

---

## Live Demo Flow (2 minutes)

### Before the Demo — Seed the Demo Data

In your terminal (or browser at `http://localhost:3000/demo`):

```bash
curl -X POST http://localhost:8000/demo/setup
```

This creates:
- A pre-populated vault for `demo@aethelgard.ai` with 5 realistic encrypted entries (bank account, life insurance, will, crypto wallet, emergency contacts)
- Status automatically advanced to `PENDING_RELEASE` — simulating a 90-day missed check-in
- A ready-to-use nominee release token (copy it from the response)

---

### Step 1 — Show the Vault (as the account owner)

Open `http://localhost:3000` and sign in as `demo@aethelgard.ai`.

The dashboard shows:
- The vault entry list (title and type only — no plaintext in the list view)
- `PENDING_RELEASE` status — the 90-day window has elapsed
- A check-in button that would reset the countdown to `ACTIVE`

**Point out**: The list endpoint intentionally returns no sensitive data. Decryption only happens on explicit single-entry fetch — there is no bulk plaintext exposure.

---

### Step 2 — Approve the Release (as the nominee)

Navigate to the nominee portal using the token from the setup response:

```
http://localhost:3000/release/{token}
```

The nominee portal shows:
- Who the vault belongs to (`demo@aethelgard.ai`)
- The nominee (`nominee@aethelgard.ai`)
- A single "Approve Legacy Release" button

Click the button. The backend:
1. Validates the 256-bit token (one-time, 72-hour expiry)
2. Marks the token `USED` (conditional DynamoDB write — cannot be reused)
3. Transitions the vault from `PENDING_RELEASE` → `RELEASED`

**Point out**: The entire nominee flow requires no admin intervention and no shared password. The token is the only credential.

---

### Step 3 — Generate the Family Guide

Sign back in as `demo@aethelgard.ai`. The status now shows `RELEASED`.

Click **Generate Family Guide**.

The backend:
1. Decrypts all five vault entries (AES-256-GCM)
2. Groups them by type (credentials, documents, notes)
3. Sends a structured prompt to **Gemini 1.5 Flash**
4. Returns a readable, human-friendly guide

**If Gemini API key is not configured**: A deterministic fallback guide is generated automatically — the system always returns a result.

---

### Optional: Architecture & System Stats

Direct reviewers to:
- `/architecture` — visual end-to-end system diagram (7 annotated nodes)
- `/judge` — live capability stats: test count, encryption details, AI status, DynamoDB config

---

## Key Technical Differentiators

| What | How |
|------|-----|
| **Plaintext never stored** | AES-256-GCM encryption before any DynamoDB write |
| **Per-user key isolation** | HKDF-SHA256 derives a unique 256-bit key per user from master secret |
| **Serverless-ready** | DynamoDB single-table PAY_PER_REQUEST, EventBridge/Lambda-ready |
| **AI with graceful fallback** | Gemini 1.5 Flash → deterministic guide if API unavailable |
| **Release security** | 256-bit URL-safe token, 72h expiry, one-time use, conditional DynamoDB write |
| **168 tests** | pytest + moto DynamoDB mock — every route, every edge case |

---

## Market & Impact

- **Market**: 3.2 million Americans die each year. Nearly all leave behind unmanaged digital accounts.
- **Problem is getting worse**: The average person now has 100+ online accounts.
- **Our solution**: Fully automated, encrypted, AI-enhanced. No manual intervention required.
- **Business model**: Freemium — free tier (5 vault entries), paid for unlimited entries, KMS encryption, and automatic nominee email delivery ($5–10/month).

---

## Path to Production

All production requirements are stubbed with `TODO (before production)` comments and documented in `DEPLOYMENT_CHECKLIST.md`. The five remaining items to launch:

1. Authentication (JWT / AWS Cognito)
2. KMS envelope encryption (replacing `LOCAL_MASTER_KEY`)
3. Nominee email delivery (SES / SendGrid)
4. Dead Man's Switch Lambda + EventBridge daily cron
5. Atomic release transition (DynamoDB `TransactWriteItems`)
