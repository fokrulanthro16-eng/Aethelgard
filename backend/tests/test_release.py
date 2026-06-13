"""Tests for the nominee release workflow."""
from datetime import datetime, timedelta, timezone

import boto3

from app.core.config import settings
from app.services.deadman import scan_dead_man_switch
from app.services.nominee import (
    approve_release,
    create_release_request,
    expire_release,
    generate_release_token,
    get_release_request,
    validate_token,
)

OWNER = "owner@example.com"
NOMINEE = "nominee@example.com"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _backdate_user(email: str, days: int) -> None:
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


def _make_pending_release_user(client, email: str = OWNER) -> None:
    """Registers a user and advances them to PENDING_RELEASE status."""
    client.post("/users", json={"email": email, "nominee_email": NOMINEE})
    _backdate_user(email, 91)
    scan_dead_man_switch()


def _expire_token_in_db(token: str) -> None:
    """Backdates a token's expires_at so it appears expired."""
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(
        settings.DYNAMODB_TABLE_NAME
    ).update_item(
        Key={"PK": f"RELEASE#{token}", "SK": "REQUEST"},
        UpdateExpression="SET expires_at = :p",
        ExpressionAttributeValues={":p": past},
    )


# ── generate_release_token ────────────────────────────────────────────────────


def test_generate_release_token_is_string():
    assert isinstance(generate_release_token(), str)


def test_generate_release_token_is_url_safe():
    token = generate_release_token()
    # URL-safe base64 uses A-Z, a-z, 0-9, -, _
    import re
    assert re.match(r"^[A-Za-z0-9\-_]+$", token)


def test_generate_release_token_sufficient_length():
    # token_urlsafe(32) produces 43 chars
    assert len(generate_release_token()) >= 40


def test_generate_release_tokens_are_unique():
    tokens = {generate_release_token() for _ in range(10)}
    assert len(tokens) == 10


# ── create_release_request ────────────────────────────────────────────────────


def test_create_release_request_succeeds_for_pending_release_user(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    assert req["token"]
    assert req["owner_email"] == OWNER
    assert req["nominee_email"] == NOMINEE
    assert req["status"] == "PENDING"


def test_create_release_request_sets_expiry(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    expires_at = datetime.fromisoformat(req["expires_at"])
    now = datetime.now(timezone.utc)
    # Should expire ~72 hours from now (allow ±60 s clock drift)
    delta_hours = (expires_at - now).total_seconds() / 3600
    assert 71 < delta_hours < 73


def test_create_release_request_fails_for_active_user(client):
    client.post("/users", json={"email": OWNER})
    try:
        create_release_request(OWNER)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "PENDING_RELEASE" in str(exc)


def test_create_release_request_fails_for_nonexistent_user(client):
    try:
        create_release_request("ghost@example.com")
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "does not exist" in str(exc)


# ── get_release_request ───────────────────────────────────────────────────────


def test_get_release_request_returns_none_for_unknown_token(client):
    assert get_release_request("nonexistent-token") is None


def test_get_release_request_returns_item_after_creation(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    fetched = get_release_request(req["token"])
    assert fetched is not None
    assert fetched["token"] == req["token"]
    assert fetched["owner_email"] == OWNER


# ── validate_token ────────────────────────────────────────────────────────────


def test_validate_token_valid_for_pending(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    result = validate_token(req["token"])
    assert result["valid"] is True
    assert result["status"] == "PENDING"


def test_validate_token_not_found_for_unknown(client):
    result = validate_token("no-such-token")
    assert result["valid"] is False
    assert result["status"] == "NOT_FOUND"
    assert result["request"] is None


def test_validate_token_expired_when_past_expiry(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    _expire_token_in_db(req["token"])
    result = validate_token(req["token"])
    assert result["valid"] is False
    assert result["status"] == "EXPIRED"


def test_validate_token_marks_expired_in_db(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    _expire_token_in_db(req["token"])
    validate_token(req["token"])
    fetched = get_release_request(req["token"])
    assert fetched["status"] == "EXPIRED"


# ── approve_release ───────────────────────────────────────────────────────────


def test_approve_release_succeeds(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    result = approve_release(req["token"])
    assert result["status"] == "USED"
    assert result.get("used_at") is not None


def test_approve_release_transitions_user_to_released(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    approve_release(req["token"])
    user = client.get(f"/users/{OWNER}").json()
    assert user["status"] == "RELEASED"


def test_approve_release_token_is_one_time_use(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    approve_release(req["token"])
    try:
        approve_release(req["token"])
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "already" in str(exc).lower() or "used" in str(exc).lower()


def test_approve_release_fails_for_unknown_token(client):
    try:
        approve_release("no-such-token")
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "not found" in str(exc).lower()


def test_approve_release_fails_for_expired_token(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    _expire_token_in_db(req["token"])
    try:
        approve_release(req["token"])
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "expired" in str(exc).lower()


# ── expire_release ────────────────────────────────────────────────────────────


def test_expire_release_marks_token_expired(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    expire_release(req["token"])
    fetched = get_release_request(req["token"])
    assert fetched["status"] == "EXPIRED"


def test_expire_release_fails_for_unknown_token(client):
    try:
        expire_release("no-such-token")
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "not found" in str(exc).lower()


# ── Admin: POST /admin/release/{email} ────────────────────────────────────────


def test_admin_create_release_returns_200(client):
    _make_pending_release_user(client)
    resp = client.post(f"/admin/release/{OWNER}")
    assert resp.status_code == 200


def test_admin_create_release_response_schema(client):
    _make_pending_release_user(client)
    data = client.post(f"/admin/release/{OWNER}").json()
    assert "token" in data
    assert "expires_at" in data
    assert data["nominee_email"] == NOMINEE


def test_admin_create_release_fails_for_active_user(client):
    client.post("/users", json={"email": OWNER})
    resp = client.post(f"/admin/release/{OWNER}")
    assert resp.status_code == 400


def test_admin_create_release_fails_for_nonexistent_user(client):
    resp = client.post("/admin/release/ghost@example.com")
    assert resp.status_code == 400


# ── GET /release/{token} ──────────────────────────────────────────────────────


def test_get_release_valid_token_returns_200(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    resp = client.get(f"/release/{req['token']}")
    assert resp.status_code == 200


def test_get_release_valid_token_response_schema(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    data = client.get(f"/release/{req['token']}").json()
    assert data["valid"] is True
    assert data["owner_email"] == OWNER
    assert data["nominee_email"] == NOMINEE
    assert data["status"] == "PENDING"


def test_get_release_unknown_token_returns_404(client):
    resp = client.get("/release/no-such-token")
    assert resp.status_code == 404


def test_get_release_expired_token_returns_200_with_valid_false(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    _expire_token_in_db(req["token"])
    resp = client.get(f"/release/{req['token']}")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert resp.json()["status"] == "EXPIRED"


# ── POST /release/{token}/approve ─────────────────────────────────────────────


def test_approve_endpoint_returns_200(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    resp = client.post(f"/release/{req['token']}/approve")
    assert resp.status_code == 200


def test_approve_endpoint_response_schema(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    data = client.post(f"/release/{req['token']}/approve").json()
    assert data["approved"] is True
    assert data["owner_email"] == OWNER
    assert "released_at" in data


def test_approve_endpoint_transitions_user(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    client.post(f"/release/{req['token']}/approve")
    assert client.get(f"/users/{OWNER}").json()["status"] == "RELEASED"


def test_approve_endpoint_used_token_returns_409(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    client.post(f"/release/{req['token']}/approve")
    resp = client.post(f"/release/{req['token']}/approve")
    assert resp.status_code == 409


def test_approve_endpoint_expired_token_returns_410(client):
    _make_pending_release_user(client)
    req = create_release_request(OWNER)
    _expire_token_in_db(req["token"])
    resp = client.post(f"/release/{req['token']}/approve")
    assert resp.status_code == 410


def test_approve_endpoint_unknown_token_returns_404(client):
    resp = client.post("/release/no-such-token/approve")
    assert resp.status_code == 404
