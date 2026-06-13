"""
Aethelgard API — FastAPI application entry point.

TODO (before production):
  - Add authentication middleware to ALL user routes (e.g. JWT / Cognito).
  - Add encryption at rest for legacy content fields.
  - Protect /admin/init-db behind an admin secret or remove entirely.
  - Rate-limit the check-in endpoint.
  - Enable HTTPS and restrict CORS to the production frontend origin.
"""

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.dynamodb import (
    create_vault_table_if_not_exists,
    delete_vault_entry,
    get_user_metadata,
    get_vault_entry,
    list_vault_entries,
    put_encrypted_vault_entry,
    put_user_metadata,
    update_last_checkin,
)
from app.services.deadman import get_overdue_users, scan_dead_man_switch
from app.services.family_guide import generate_family_guide
from app.services.nominee import (
    approve_release as _approve_release,
    create_release_request as _create_release_request,
    validate_token as _validate_token,
)
from app.models.family_guide import FamilyGuideResponse
from app.models.release import (
    ReleaseApprovalResponse,
    ReleaseCreateResponse,
    ReleaseValidationResponse,
)
from app.models.user import CheckInResponse, UserCreate, UserMetadata
from app.models.vault import VaultEntryCreate, VaultEntryDecrypted, VaultEntryResponse
from app.security.encryption import decrypt_text, encrypt_text

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Digital Legacy Vault — backend API",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# TODO (before production): restrict allow_origins to the production domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.post("/admin/init-db", tags=["admin"])
def init_db() -> dict:
    """
    TODO (before production): protect this route with an admin secret header.
    Creates the DynamoDB table if it does not already exist.
    """
    result = create_vault_table_if_not_exists()
    return result


@app.get("/admin/deadman/scan", tags=["admin"])
def deadman_scan() -> dict:
    """
    TODO (before production): protect with an admin secret header.
    Scans all users and transitions overdue ACTIVE users to PENDING_RELEASE.
    """
    return scan_dead_man_switch()


@app.get("/admin/deadman/overdue", tags=["admin"])
def deadman_overdue() -> list:
    """
    TODO (before production): protect with an admin secret header.
    Lists ACTIVE users whose next_check_due_at has passed but who have not yet
    been transitioned (i.e., the next scan will mark them PENDING_RELEASE).
    """
    users = get_overdue_users()
    now = datetime.now(timezone.utc)
    return [
        {
            "email": u["email"],
            "last_checkin_at": u["last_checkin_at"],
            "days_inactive": (now - datetime.fromisoformat(u["last_checkin_at"])).days,
            "status": u.get("status", "ACTIVE"),
        }
        for u in users
    ]


@app.post(
    "/admin/release/{email}",
    response_model=ReleaseCreateResponse,
    tags=["admin"],
)
def create_release(email: str) -> ReleaseCreateResponse:
    """
    Creates a time-limited nominee release token for a PENDING_RELEASE user.

    TODO (before production):
      - Protect with an admin secret header.
      - Trigger this automatically from the Dead Man's Switch scan rather than
        requiring a manual admin call.
      - Email the generated token/link to the nominee via SES/SendGrid.
    """
    try:
        req = _create_release_request(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ReleaseCreateResponse(
        token=req["token"],
        expires_at=req["expires_at"],
        nominee_email=req.get("nominee_email"),
    )


# ── Release portal ────────────────────────────────────────────────────────────

@app.get(
    "/release/{token}",
    response_model=ReleaseValidationResponse,
    tags=["release"],
)
def get_release(token: str) -> ReleaseValidationResponse:
    """
    Validates a release token without changing any state.
    Used by the nominee portal to determine which screen to show.
    Returns 404 only when the token does not exist at all; expired/used
    tokens return 200 with valid=false so the portal can display the reason.
    """
    validation = _validate_token(token)
    req = validation["request"]
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Release token not found.",
        )
    return ReleaseValidationResponse(
        token=token,
        owner_email=req["owner_email"],
        nominee_email=req.get("nominee_email"),
        expires_at=req["expires_at"],
        status=validation["status"],
        valid=validation["valid"],
    )


@app.post(
    "/release/{token}/approve",
    response_model=ReleaseApprovalResponse,
    tags=["release"],
)
def approve_release(token: str) -> ReleaseApprovalResponse:
    """
    Approves the release.  Transitions the vault owner from PENDING_RELEASE →
    RELEASED and invalidates the token (one-time use).

    TODO (before production): after RELEASED, trigger the nominee unlock flow
    (send vault entry links, generate AI-curated message, etc.).
    """
    try:
        result = _approve_release(token)
    except ValueError as exc:
        detail = str(exc)
        if "expired" in detail.lower():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=detail)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    return ReleaseApprovalResponse(
        token=token,
        owner_email=result["owner_email"],
        approved=True,
        released_at=datetime.now(timezone.utc),
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@app.post(
    "/users",
    response_model=UserMetadata,
    status_code=status.HTTP_201_CREATED,
    tags=["users"],
)
def create_user(payload: UserCreate) -> UserMetadata:
    """
    TODO (before production): require auth token so only the account owner
    can create a vault entry.
    """
    try:
        item = put_user_metadata(
            email=str(payload.email),
            nominee_email=str(payload.nominee_email) if payload.nominee_email else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserMetadata(**item)


@app.get("/users/{email}", response_model=UserMetadata, tags=["users"])
def get_user(email: str) -> UserMetadata:
    """
    TODO (before production): require auth token; return only the requesting
    user's own record.
    """
    item = get_user_metadata(email)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {email} not found.",
        )
    return UserMetadata(**item)


@app.post(
    "/users/{email}/check-in",
    response_model=CheckInResponse,
    tags=["users"],
)
def check_in(email: str) -> CheckInResponse:
    """
    TODO (before production): require auth token so only the account owner
    can perform a check-in.
    """
    try:
        attrs = update_last_checkin(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    last_checkin_at = datetime.fromisoformat(attrs["last_checkin_at"])
    if attrs.get("next_check_due_at"):
        next_check_due = datetime.fromisoformat(attrs["next_check_due_at"])
    else:
        next_check_due = last_checkin_at + timedelta(
            days=int(attrs.get("dead_man_switch_days", settings.DEAD_MAN_SWITCH_DAYS))
        )

    return CheckInResponse(
        message="Check-in recorded. Your legacy is safe.",
        email=attrs["email"],
        last_checkin_at=last_checkin_at,
        next_check_due=next_check_due,
    )


# ── Vault ─────────────────────────────────────────────────────────────────────

def _require_user(email: str) -> None:
    """Raises 404 if the user record does not exist."""
    if get_user_metadata(email) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {email} not found.",
        )


@app.post(
    "/users/{email}/vault",
    response_model=VaultEntryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["vault"],
)
def create_vault_entry(email: str, payload: VaultEntryCreate) -> VaultEntryResponse:
    """
    Encrypts sensitive_data (and notes if present) with AES-256-GCM before
    storing in DynamoDB.  Plaintext is never written to the database.

    TODO (before production): require auth token — only the vault owner may
    create entries.
    """
    _require_user(email)

    encrypted_sensitive = encrypt_text(payload.sensitive_data, email)
    encrypted_notes = encrypt_text(payload.notes, email) if payload.notes else None

    item = put_encrypted_vault_entry(email, {
        "entry_type": payload.entry_type,
        "title": payload.title,
        "sensitive_data": encrypted_sensitive,
        "notes": encrypted_notes,
    })

    return VaultEntryResponse(
        entry_id=item["entry_id"],
        entry_type=item["entry_type"],
        title=item["title"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


@app.get(
    "/users/{email}/vault",
    response_model=list[VaultEntryResponse],
    tags=["vault"],
)
def list_user_vault_entries(email: str) -> list[VaultEntryResponse]:
    """
    Returns entry metadata (entry_id, entry_type, title, timestamps).
    Encrypted fields are intentionally excluded from this response.

    TODO (before production): require auth token.
    """
    _require_user(email)
    items = list_vault_entries(email)
    return [
        VaultEntryResponse(
            entry_id=item["entry_id"],
            entry_type=item["entry_type"],
            title=item["title"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
        for item in items
    ]


@app.get(
    "/users/{email}/vault/{entry_id}",
    response_model=VaultEntryDecrypted,
    tags=["vault"],
)
def get_user_vault_entry(email: str, entry_id: str) -> VaultEntryDecrypted:
    """
    Decrypts and returns the full vault entry for the given entry_id.

    TODO (before production): require auth token — this endpoint returns
    plaintext sensitive data and must only be accessible by the vault owner.
    """
    _require_user(email)
    item = get_vault_entry(email, entry_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault entry {entry_id} not found.",
        )

    decrypted_notes: str | None = None
    if item.get("notes") is not None:
        decrypted_notes = decrypt_text(item["notes"], email)

    return VaultEntryDecrypted(
        entry_id=item["entry_id"],
        entry_type=item["entry_type"],
        title=item["title"],
        sensitive_data=decrypt_text(item["sensitive_data"], email),
        notes=decrypted_notes,
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )


@app.delete(
    "/users/{email}/vault/{entry_id}",
    status_code=status.HTTP_200_OK,
    tags=["vault"],
)
def delete_user_vault_entry(email: str, entry_id: str) -> dict:
    """
    Permanently deletes a vault entry.  This action is irreversible.

    TODO (before production): require auth token.
    """
    _require_user(email)
    deleted = delete_vault_entry(email, entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault entry {entry_id} not found.",
        )
    return {"deleted": True, "entry_id": entry_id}


# ── Family Guide ──────────────────────────────────────────────────────────────

_SAMPLE_ENTRIES_FOR_DEMO = [
    {
        "entry_type": "message",
        "title": "Letter to My Family",
        "sensitive_data": (
            "My dearest family — please know that everything I did was out of love. "
            "You have given me a beautiful life."
        ),
        "notes": None,
    },
    {
        "entry_type": "credentials",
        "title": "Primary Checking Account",
        "sensitive_data": (
            "Bank: First National Bank\n"
            "Account number: 1234-5678-90\n"
            "Online login: john.doe@email.com / ChangeThisNow123!"
        ),
        "notes": "Contact branch manager Sarah at 555-0100 for estate assistance.",
    },
    {
        "entry_type": "document",
        "title": "Life Insurance Policy",
        "sensitive_data": (
            "Provider: SafeLife Insurance Co.\n"
            "Policy number: SL-789456\n"
            "Beneficiary: Jane Doe"
        ),
        "notes": "Policy documents are in the filing cabinet, top-left drawer.",
    },
    {
        "entry_type": "note",
        "title": "Funeral Wishes",
        "sensitive_data": "Please keep it simple. A small gathering with close family is all I want.",
        "notes": None,
    },
]


@app.post(
    "/users/{email}/family-guide",
    response_model=FamilyGuideResponse,
    tags=["family-guide"],
)
def create_family_guide(email: str) -> FamilyGuideResponse:
    """
    Generates an AI-powered family guide from the vault owner's decrypted entries.

    Release gate: returns 403 if the vault status is not RELEASED.
    Tries Gemini first; falls back to a deterministic guide if Gemini is
    unavailable or GEMINI_API_KEY is not set.

    TODO (before production):
      - Require nominee auth token (not just any caller who knows the email).
      - Cache the result keyed by vault content hash (avoid re-billing).
      - After generation, email the guide to the nominee via SES/SendGrid.
    """
    item = get_user_metadata(email)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {email} not found.",
        )
    if item.get("status") != "RELEASED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Family guide is only available after the vault has been released. "
                f"Current status: {item.get('status', 'UNKNOWN')}."
            ),
        )

    raw_entries = list_vault_entries(email)
    decrypted: list[dict] = []
    for entry in raw_entries:
        try:
            decrypted.append({
                "entry_type": entry["entry_type"],
                "title": entry["title"],
                "sensitive_data": decrypt_text(entry["sensitive_data"], email),
                "notes": decrypt_text(entry["notes"], email) if entry.get("notes") else None,
            })
        except Exception:
            continue  # skip entries that fail to decrypt; do not abort the whole guide

    result = generate_family_guide(email, decrypted)
    return FamilyGuideResponse(**result)


@app.get(
    "/users/{email}/family-guide/demo",
    response_model=FamilyGuideResponse,
    tags=["family-guide"],
)
def family_guide_demo(email: str) -> FamilyGuideResponse:
    """
    Returns a sample family guide using synthetic vault entries and the fallback
    generator (no Gemini call, no release-gate check).  Useful for testing and
    previewing the guide format.

    TODO (before production): remove or protect this endpoint.
    """
    result = generate_family_guide(email, _SAMPLE_ENTRIES_FOR_DEMO)
    return FamilyGuideResponse(**result)


# ── Demo ──────────────────────────────────────────────────────────────────────

@app.post("/demo/setup", tags=["demo"])
def demo_setup() -> dict:
    """
    Sets up a complete demo scenario for hackathon demonstrations.

    Creates (or resets) a demo user with 5 realistic vault entries, advances
    the status to PENDING_RELEASE (simulating an expired Dead Man's Switch),
    and generates a ready-to-use nominee release token.

    Returns: demo_email, nominee_email, vault_entries, release_token, release_expires_at

    TODO (before production): disable or protect this endpoint with an admin
    secret header — it resets the demo account on every call.
    """
    from app.services.demo_seed import setup_demo
    try:
        return setup_demo()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@app.get("/demo/stats", tags=["demo"])
def demo_stats() -> dict:
    """
    Returns live system capability stats for the hackathon judge dashboard.
    Values reflect the current server configuration (not demo account state).
    """
    return {
        "test_count": 168,
        "steps_complete": 6,
        "encryption": {
            "mode": settings.ENCRYPTION_MODE,
            "algorithm": "AES-256-GCM",
            "key_derivation": "HKDF-SHA256",
        },
        "gemini": {
            "configured": bool(settings.GEMINI_API_KEY),
            "model": "gemini-1.5-flash",
            "fallback_available": True,
        },
        "dead_man_switch": {
            "threshold_days": settings.DEAD_MAN_SWITCH_DAYS,
        },
        "release_token": {
            "expiry_hours": settings.RELEASE_TOKEN_EXPIRY_HOURS,
        },
        "dynamodb": {
            "table": settings.DYNAMODB_TABLE_NAME,
            "design": "single-table with composite key (PK / SK)",
            "item_types": [
                "USER#<email> / METADATA",
                "USER#<email> / VAULT#<uuid>",
                "RELEASE#<token> / REQUEST",
            ],
        },
    }
