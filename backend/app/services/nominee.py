"""
Nominee Release Portal service for Aethelgard.

Handles the release workflow after Dead Man's Switch fires:
  PENDING_RELEASE  →  (nominee clicks approval link)  →  RELEASED

The token is URL-safe, 256 bits of entropy, and expires after
RELEASE_TOKEN_EXPIRY_HOURS hours (default 72 h / 3 days).

TODO (production):
  - Email the nominee their approval link via SES/SendGrid when
    create_release_request() is called (currently the token is only
    returned via the admin API).
  - Use DynamoDB TransactWriteItems in approve_release() so that
    mark_release_used + mark_released are a single atomic operation.
    A crash between the two steps currently leaves the token USED but
    the user still PENDING_RELEASE.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.db.dynamodb import (
    get_release_request as _db_get_release_request,
    get_user_metadata,
    mark_release_expired,
    mark_release_used,
    mark_released,
    put_release_request,
)


def generate_release_token() -> str:
    """Generates a cryptographically secure, URL-safe token (256 bits)."""
    return secrets.token_urlsafe(32)


def create_release_request(owner_email: str) -> dict[str, Any]:
    """
    Creates a release request for an owner in PENDING_RELEASE status.
    Raises ValueError if the user does not exist or is not PENDING_RELEASE.
    """
    user = get_user_metadata(owner_email)
    if user is None:
        raise ValueError(f"User {owner_email} does not exist.")
    if user.get("status") != "PENDING_RELEASE":
        raise ValueError(
            f"User {owner_email} is not in PENDING_RELEASE status "
            f"(current: {user.get('status', 'UNKNOWN')})."
        )

    token = generate_release_token()
    now_dt = datetime.now(timezone.utc)
    expires_at = (now_dt + timedelta(hours=settings.RELEASE_TOKEN_EXPIRY_HOURS)).isoformat()

    return put_release_request(
        token=token,
        owner_email=owner_email,
        nominee_email=user.get("nominee_email"),
        expires_at=expires_at,
    )


def get_release_request(token: str) -> dict[str, Any] | None:
    return _db_get_release_request(token)


def validate_token(token: str) -> dict[str, Any]:
    """
    Validates a release token without changing any state (unless the token
    has silently expired, in which case it is marked EXPIRED).

    Returns:
        {
            "valid": bool,
            "status": "PENDING" | "USED" | "EXPIRED" | "NOT_FOUND",
            "request": dict | None
        }
    """
    request = _db_get_release_request(token)
    if request is None:
        return {"valid": False, "status": "NOT_FOUND", "request": None}

    current_status = request.get("status", "PENDING")
    if current_status == "USED":
        return {"valid": False, "status": "USED", "request": request}
    if current_status == "EXPIRED":
        return {"valid": False, "status": "EXPIRED", "request": request}

    # Check wall-clock expiry even if status is still PENDING
    expires_at = datetime.fromisoformat(request["expires_at"])
    if datetime.now(timezone.utc) >= expires_at:
        try:
            mark_release_expired(token)
        except ValueError:
            pass  # already gone — fine
        return {"valid": False, "status": "EXPIRED", "request": request}

    return {"valid": True, "status": "PENDING", "request": request}


def approve_release(token: str) -> dict[str, Any]:
    """
    Approves the release:
    1. Validates the token (must be PENDING and not expired).
    2. Marks the token USED (one-time, conditional write).
    3. Transitions the owner's vault status from PENDING_RELEASE → RELEASED.

    Returns the updated release request attributes.

    Raises ValueError on any invalid condition (not found / used / expired).

    TODO (production): Wrap steps 2 and 3 in DynamoDB TransactWriteItems to
    make the transition atomic.
    """
    validation = validate_token(token)
    if not validation["valid"]:
        msg_map = {
            "NOT_FOUND": "Release token not found.",
            "USED": "Release token has already been used.",
            "EXPIRED": "Release token has expired.",
        }
        raise ValueError(msg_map.get(validation["status"], "Release token is not valid."))

    request = validation["request"]
    now = datetime.now(timezone.utc).isoformat()

    # Step 2: mark token used (conditional — safe against concurrent requests)
    updated_request = mark_release_used(token, used_at=now)

    # Step 3: transition owner to RELEASED
    try:
        mark_released(request["owner_email"])
    except ValueError:
        # User already RELEASED (e.g., via another token) — acceptable end state
        pass

    return updated_request


def expire_release(token: str) -> dict[str, Any]:
    """
    Explicitly expires a release token.
    Raises ValueError if the token does not exist.
    """
    return mark_release_expired(token)
