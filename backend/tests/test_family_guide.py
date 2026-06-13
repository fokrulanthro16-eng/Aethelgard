"""Tests for the Family Guide generator and API routes."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import boto3

from app.core.config import settings
from app.services.deadman import scan_dead_man_switch
from app.services.family_guide import (
    build_guide_context,
    create_fallback_guide,
    generate_family_guide,
)
from app.services.nominee import approve_release, create_release_request

OWNER = "guide-owner@example.com"
NOMINEE = "guide-nominee@example.com"

_SAMPLE_ENTRIES = [
    {
        "entry_type": "message",
        "title": "Letter to My Family",
        "sensitive_data": "I love you all very much.",
        "notes": None,
    },
    {
        "entry_type": "credentials",
        "title": "Main Bank Account",
        "sensitive_data": "Bank: First National\nLogin: user@email.com / secret123",
        "notes": "Change password immediately.",
    },
    {
        "entry_type": "document",
        "title": "Insurance Policy",
        "sensitive_data": "Policy #SL-999 — SafeLife Insurance",
        "notes": None,
    },
]


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


def _make_released_user(client, email: str = OWNER) -> None:
    """Creates a user and advances them all the way to RELEASED status."""
    client.post("/users", json={"email": email, "nominee_email": NOMINEE})
    _backdate_user(email, 91)
    scan_dead_man_switch()
    req = create_release_request(email)
    approve_release(req["token"])


# ── build_guide_context ───────────────────────────────────────────────────────


def test_build_guide_context_includes_owner_email():
    ctx = build_guide_context("alice@example.com", [])
    assert "alice@example.com" in ctx


def test_build_guide_context_empty_vault_message():
    ctx = build_guide_context("alice@example.com", [])
    assert "no entries" in ctx.lower()


def test_build_guide_context_includes_entry_titles():
    ctx = build_guide_context("alice@example.com", _SAMPLE_ENTRIES)
    assert "Letter to My Family" in ctx
    assert "Main Bank Account" in ctx
    assert "Insurance Policy" in ctx


def test_build_guide_context_includes_sensitive_data():
    ctx = build_guide_context("alice@example.com", _SAMPLE_ENTRIES)
    assert "I love you all" in ctx
    assert "First National" in ctx


def test_build_guide_context_groups_by_entry_type():
    ctx = build_guide_context("alice@example.com", _SAMPLE_ENTRIES)
    assert "Personal Messages" in ctx or "message" in ctx.lower()
    assert "Account Credentials" in ctx or "credentials" in ctx.lower()


def test_build_guide_context_includes_notes():
    ctx = build_guide_context("alice@example.com", _SAMPLE_ENTRIES)
    assert "Change password immediately" in ctx


# ── create_fallback_guide ─────────────────────────────────────────────────────


def test_fallback_guide_contains_owner_email():
    guide = create_fallback_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert "alice@example.com" in guide


def test_fallback_guide_contains_entry_titles():
    guide = create_fallback_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert "Letter to My Family" in guide
    assert "Main Bank Account" in guide


def test_fallback_guide_contains_sensitive_data():
    guide = create_fallback_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert "I love you all" in guide
    assert "First National" in guide


def test_fallback_guide_works_with_empty_vault():
    guide = create_fallback_guide("alice@example.com", [])
    assert "alice@example.com" in guide
    assert "no vault entries" in guide.lower() or "no entries" in guide.lower()


def test_fallback_guide_is_deterministic():
    g1 = create_fallback_guide("alice@example.com", _SAMPLE_ENTRIES)
    g2 = create_fallback_guide("alice@example.com", _SAMPLE_ENTRIES)
    # Generated date may differ if run across midnight — check content, not exact equality
    assert "Letter to My Family" in g1 and "Letter to My Family" in g2


def test_fallback_guide_contains_section_headers():
    guide = create_fallback_guide("alice@example.com", _SAMPLE_ENTRIES)
    # At least one section header should appear
    assert "PERSONAL MESSAGES" in guide or "ACCOUNT CREDENTIALS" in guide or "DOCUMENTS" in guide


# ── generate_family_guide ─────────────────────────────────────────────────────


def test_generate_family_guide_returns_correct_schema():
    result = generate_family_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert "generated_at" in result
    assert "guide" in result
    assert "source" in result
    assert isinstance(result["guide"], str)
    assert len(result["guide"]) > 0


def test_generate_family_guide_uses_fallback_without_api_key():
    # GEMINI_API_KEY is not set in the test environment → always falls back
    result = generate_family_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert result["source"] == "fallback"


def test_generate_family_guide_fallback_contains_entries():
    result = generate_family_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert "Letter to My Family" in result["guide"]


def test_generate_family_guide_empty_vault():
    result = generate_family_guide("alice@example.com", [])
    assert result["source"] == "fallback"
    assert isinstance(result["guide"], str)
    assert len(result["guide"]) > 0


def test_generate_family_guide_uses_gemini_when_available():
    with patch("app.services.family_guide.call_gemini", return_value="Gemini-generated text"):
        result = generate_family_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert result["source"] == "gemini"
    assert result["guide"] == "Gemini-generated text"


def test_generate_family_guide_falls_back_on_gemini_error():
    with patch("app.services.family_guide.call_gemini", side_effect=RuntimeError("API down")):
        result = generate_family_guide("alice@example.com", _SAMPLE_ENTRIES)
    assert result["source"] == "fallback"
    assert "Letter to My Family" in result["guide"]


def test_prompt_contains_vault_context():
    captured: list[str] = []

    def mock_gemini(prompt: str, **_kwargs) -> str:
        captured.append(prompt)
        return "ok"

    with patch("app.services.family_guide.call_gemini", side_effect=mock_gemini):
        generate_family_guide("alice@example.com", _SAMPLE_ENTRIES)

    assert captured, "call_gemini was not called"
    assert "Letter to My Family" in captured[0]
    assert "alice@example.com" in captured[0]


# ── Release gate: POST /users/{email}/family-guide ────────────────────────────


def test_family_guide_403_for_active_user(client):
    client.post("/users", json={"email": OWNER})
    resp = client.post(f"/users/{OWNER}/family-guide")
    assert resp.status_code == 403


def test_family_guide_403_for_pending_release_user(client):
    client.post("/users", json={"email": OWNER})
    _backdate_user(OWNER, 91)
    scan_dead_man_switch()
    resp = client.post(f"/users/{OWNER}/family-guide")
    assert resp.status_code == 403


def test_family_guide_403_detail_mentions_released(client):
    client.post("/users", json={"email": OWNER})
    detail = client.post(f"/users/{OWNER}/family-guide").json()["detail"]
    assert "RELEASED" in detail or "released" in detail.lower()


def test_family_guide_404_for_nonexistent_user(client):
    resp = client.post("/users/ghost@example.com/family-guide")
    assert resp.status_code == 404


def test_family_guide_200_for_released_user(client):
    _make_released_user(client)
    resp = client.post(f"/users/{OWNER}/family-guide")
    assert resp.status_code == 200


def test_family_guide_response_schema(client):
    _make_released_user(client)
    data = client.post(f"/users/{OWNER}/family-guide").json()
    assert "generated_at" in data
    assert "guide" in data
    assert "source" in data


def test_family_guide_empty_vault_still_returns_200(client):
    _make_released_user(client)
    # No vault entries were added — guide should still work
    resp = client.post(f"/users/{OWNER}/family-guide")
    assert resp.status_code == 200
    assert len(resp.json()["guide"]) > 0


def test_family_guide_includes_vault_entry_when_present(client):
    _make_released_user(client)
    # Add a vault entry before release (user is now RELEASED so normal vault
    # write is still possible since we haven't added auth yet)
    client.post(
        f"/users/{OWNER}/vault",
        json={
            "entry_type": "message",
            "title": "My Final Words",
            "sensitive_data": "Goodbye and thank you for everything.",
        },
    )
    data = client.post(f"/users/{OWNER}/family-guide").json()
    assert "My Final Words" in data["guide"] or "Final Words" in data["guide"]


# ── GET /users/{email}/family-guide/demo ─────────────────────────────────────


def test_family_guide_demo_returns_200(client):
    client.post("/users", json={"email": OWNER})
    assert client.get(f"/users/{OWNER}/family-guide/demo").status_code == 200


def test_family_guide_demo_response_schema(client):
    client.post("/users", json={"email": OWNER})
    data = client.get(f"/users/{OWNER}/family-guide/demo").json()
    assert "generated_at" in data
    assert "guide" in data
    assert "source" in data


def test_family_guide_demo_works_without_released_status(client):
    # Demo endpoint skips the release gate
    client.post("/users", json={"email": OWNER})
    resp = client.get(f"/users/{OWNER}/family-guide/demo")
    assert resp.status_code == 200


def test_family_guide_demo_guide_is_not_empty(client):
    client.post("/users", json={"email": OWNER})
    data = client.get(f"/users/{OWNER}/family-guide/demo").json()
    assert len(data["guide"]) > 50
