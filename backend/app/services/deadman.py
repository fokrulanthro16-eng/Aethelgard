"""
Dead Man's Switch engine for Aethelgard.

Status lifecycle:
  ACTIVE  →  (no check-in for dead_man_switch_days)  →  PENDING_RELEASE
  PENDING_RELEASE  →  (future: nominee unlock flow)   →  RELEASED

This module handles detection and the ACTIVE → PENDING_RELEASE transition only.
It does NOT release vault contents — that requires a separate authenticated flow.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.db.dynamodb import mark_pending_release, scan_all_user_metadata

STATUS_ACTIVE = "ACTIVE"
STATUS_PENDING_RELEASE = "PENDING_RELEASE"
STATUS_RELEASED = "RELEASED"  # future — not yet implemented


def calculate_next_due_date(
    last_checkin_at: datetime,
    threshold_days: int | None = None,
) -> datetime:
    days = threshold_days if threshold_days is not None else settings.DEAD_MAN_SWITCH_DAYS
    return last_checkin_at + timedelta(days=days)


def is_overdue(last_checkin_at: datetime, threshold_days: int | None = None) -> bool:
    return datetime.now(timezone.utc) >= calculate_next_due_date(last_checkin_at, threshold_days)


def get_overdue_users() -> list[dict[str, Any]]:
    """
    Scans all user METADATA records and returns those that are ACTIVE and whose
    next_check_due_at has already passed.

    TODO (production): Replace the full-table scan with a GSI query on
    status + next_check_due_at so this runs in O(overdue) rather than O(all users).
    """
    users = scan_all_user_metadata()
    now = datetime.now(timezone.utc)
    overdue: list[dict[str, Any]] = []

    for user in users:
        if user.get("status") != STATUS_ACTIVE:
            continue

        next_due_raw = user.get("next_check_due_at")
        if next_due_raw:
            next_due = datetime.fromisoformat(next_due_raw)
        else:
            # Fallback for items created before next_check_due_at was stored
            last = datetime.fromisoformat(user["last_checkin_at"])
            switch_days = int(user.get("dead_man_switch_days", settings.DEAD_MAN_SWITCH_DAYS))
            next_due = calculate_next_due_date(last, switch_days)

        if now >= next_due:
            overdue.append(user)

    return overdue


def scan_dead_man_switch() -> dict[str, Any]:
    """
    Full scan: finds all overdue ACTIVE users and transitions them to PENDING_RELEASE.
    Returns a summary dict with counts and any per-user errors.
    """
    all_users = scan_all_user_metadata()
    overdue = get_overdue_users()

    updated: list[str] = []
    errors: list[dict[str, str]] = []

    for user in overdue:
        email = user["email"]
        try:
            mark_pending_release(email)
            updated.append(email)
        except ValueError:
            # Already PENDING_RELEASE or user vanished between scan and update — skip
            pass
        except Exception as exc:
            errors.append({"email": email, "error": str(exc)})

    return {
        "scanned_users": len(all_users),
        "overdue_users": len(overdue),
        "updated_users": len(updated),
        "errors": errors,
    }
