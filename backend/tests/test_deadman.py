"""Tests for the Dead Man's Switch engine and admin endpoints."""
from datetime import datetime, timedelta, timezone

import boto3

from app.core.config import settings
from app.services.deadman import (
    calculate_next_due_date,
    get_overdue_users,
    is_overdue,
    scan_dead_man_switch,
)

EMAIL = "deadman@example.com"


def _backdate_user(email: str, days: int) -> None:
    """Rewinds a user's last_checkin_at and next_check_due_at by N days."""
    now = datetime.now(timezone.utc)
    last = now - timedelta(days=days)
    next_due = last + timedelta(days=settings.DEAD_MAN_SWITCH_DAYS)
    boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_TABLE_NAME
    ).update_item(
        Key={"PK": f"USER#{email.lower()}", "SK": "METADATA"},
        UpdateExpression="SET last_checkin_at = :l, next_check_due_at = :n",
        ExpressionAttributeValues={
            ":l": last.isoformat(),
            ":n": next_due.isoformat(),
        },
    )


# ── calculate_next_due_date ───────────────────────────────────────────────────


def test_next_due_date_is_90_days_ahead():
    now = datetime.now(timezone.utc)
    due = calculate_next_due_date(now)
    assert (due - now).days == 90


def test_next_due_date_uses_custom_threshold():
    now = datetime.now(timezone.utc)
    due = calculate_next_due_date(now, threshold_days=30)
    assert (due - now).days == 30


# ── is_overdue ────────────────────────────────────────────────────────────────


def test_89_days_not_overdue():
    last = datetime.now(timezone.utc) - timedelta(days=89)
    assert is_overdue(last, threshold_days=90) is False


def test_90_days_is_overdue():
    # 90 days + 1 second ensures we are past the exact boundary
    last = datetime.now(timezone.utc) - timedelta(days=90, seconds=1)
    assert is_overdue(last, threshold_days=90) is True


def test_91_days_is_overdue():
    last = datetime.now(timezone.utc) - timedelta(days=91)
    assert is_overdue(last, threshold_days=90) is True


# ── get_overdue_users ─────────────────────────────────────────────────────────


def test_get_overdue_users_empty_with_no_users(client):
    assert get_overdue_users() == []


def test_fresh_user_is_not_overdue(client):
    client.post("/users", json={"email": EMAIL})
    assert get_overdue_users() == []


def test_91_day_inactive_user_is_detected(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    overdue = get_overdue_users()
    assert len(overdue) == 1
    assert overdue[0]["email"] == EMAIL


def test_pending_release_user_excluded_from_overdue(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    # Manually transition to PENDING_RELEASE via the scan
    scan_dead_man_switch()
    # Second call to get_overdue_users should return nothing (already transitioned)
    assert get_overdue_users() == []


# ── scan_dead_man_switch ──────────────────────────────────────────────────────


def test_scan_returns_expected_keys(client):
    result = scan_dead_man_switch()
    assert "scanned_users" in result
    assert "overdue_users" in result
    assert "updated_users" in result
    assert "errors" in result


def test_scan_zero_counts_when_no_users(client):
    result = scan_dead_man_switch()
    assert result["scanned_users"] == 0
    assert result["overdue_users"] == 0
    assert result["updated_users"] == 0


def test_scan_transitions_overdue_user(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    result = scan_dead_man_switch()
    assert result["overdue_users"] == 1
    assert result["updated_users"] == 1


def test_scan_sets_status_to_pending_release(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    scan_dead_man_switch()
    user = client.get(f"/users/{EMAIL}").json()
    assert user["status"] == "PENDING_RELEASE"


def test_scan_does_not_double_transition(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    scan_dead_man_switch()
    # Second scan: user is already PENDING_RELEASE — nothing new updated
    result = scan_dead_man_switch()
    assert result["updated_users"] == 0


def test_non_overdue_user_stays_active_after_scan(client):
    client.post("/users", json={"email": EMAIL})
    # No backdating — fresh user
    result = scan_dead_man_switch()
    assert result["updated_users"] == 0
    assert client.get(f"/users/{EMAIL}").json()["status"] == "ACTIVE"


# ── Check-in resets status ────────────────────────────────────────────────────


def test_checkin_resets_pending_release_to_active(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    scan_dead_man_switch()
    assert client.get(f"/users/{EMAIL}").json()["status"] == "PENDING_RELEASE"

    client.post(f"/users/{EMAIL}/check-in")
    assert client.get(f"/users/{EMAIL}").json()["status"] == "ACTIVE"


def test_checkin_updates_next_check_due_at(client):
    from datetime import datetime
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    checkin = client.post(f"/users/{EMAIL}/check-in").json()
    user = client.get(f"/users/{EMAIL}").json()
    # next_check_due_at in DB should be ~90 days after now
    next_due = datetime.fromisoformat(user["next_check_due_at"])
    now = datetime.now(timezone.utc)
    delta_days = (next_due - now).days
    assert 89 <= delta_days <= 90


# ── Admin endpoints ───────────────────────────────────────────────────────────


def test_admin_deadman_scan_200(client):
    assert client.get("/admin/deadman/scan").status_code == 200


def test_admin_deadman_scan_response_keys(client):
    data = client.get("/admin/deadman/scan").json()
    assert "scanned_users" in data
    assert "overdue_users" in data
    assert "updated_users" in data


def test_admin_deadman_overdue_200(client):
    assert client.get("/admin/deadman/overdue").status_code == 200


def test_admin_deadman_overdue_empty(client):
    assert client.get("/admin/deadman/overdue").json() == []


def test_admin_deadman_overdue_lists_inactive_user(client):
    client.post("/users", json={"email": EMAIL})
    _backdate_user(EMAIL, 91)
    data = client.get("/admin/deadman/overdue").json()
    assert len(data) == 1
    item = data[0]
    assert item["email"] == EMAIL
    assert item["days_inactive"] >= 91
    assert item["status"] == "ACTIVE"
