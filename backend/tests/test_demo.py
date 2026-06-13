"""Tests for the Hackathon Demo Mode endpoints (/demo/setup, /demo/stats)."""

DEMO_EMAIL = "demo@aethelgard.ai"
DEMO_NOMINEE = "nominee@aethelgard.ai"


# ── POST /demo/setup ──────────────────────────────────────────────────────────


def test_demo_setup_returns_200(client):
    assert client.post("/demo/setup").status_code == 200


def test_demo_setup_response_has_demo_email(client):
    data = client.post("/demo/setup").json()
    assert data["demo_email"] == DEMO_EMAIL


def test_demo_setup_response_has_nominee_email(client):
    data = client.post("/demo/setup").json()
    assert data["nominee_email"] == DEMO_NOMINEE


def test_demo_setup_response_has_release_token(client):
    data = client.post("/demo/setup").json()
    assert "release_token" in data
    assert len(data["release_token"]) > 0


def test_demo_setup_response_has_expires_at(client):
    data = client.post("/demo/setup").json()
    assert "release_expires_at" in data


def test_demo_setup_creates_five_vault_entries(client):
    data = client.post("/demo/setup").json()
    assert len(data["vault_entries"]) == 5


def test_demo_setup_vault_entries_have_correct_schema(client):
    data = client.post("/demo/setup").json()
    for entry in data["vault_entries"]:
        assert "entry_id" in entry
        assert "entry_type" in entry
        assert "title" in entry


def test_demo_setup_vault_entries_cover_all_types(client):
    data = client.post("/demo/setup").json()
    types = {e["entry_type"] for e in data["vault_entries"]}
    assert "credentials" in types
    assert "document" in types
    assert "note" in types


def test_demo_setup_creates_pending_release_user(client):
    client.post("/demo/setup")
    user = client.get(f"/users/{DEMO_EMAIL}").json()
    assert user["status"] == "PENDING_RELEASE"


def test_demo_setup_release_token_validates(client):
    data = client.post("/demo/setup").json()
    token = data["release_token"]
    validation = client.get(f"/release/{token}").json()
    assert validation["valid"] is True
    assert validation["status"] == "PENDING"


def test_demo_setup_is_idempotent(client):
    client.post("/demo/setup")
    resp = client.post("/demo/setup")
    assert resp.status_code == 200


def test_demo_setup_idempotent_resets_vault_entries(client):
    first = client.post("/demo/setup").json()
    second = client.post("/demo/setup").json()
    first_ids = {e["entry_id"] for e in first["vault_entries"]}
    second_ids = {e["entry_id"] for e in second["vault_entries"]}
    assert not first_ids.intersection(second_ids), "Each call should create fresh entry IDs"


# ── GET /demo/stats ───────────────────────────────────────────────────────────


def test_demo_stats_returns_200(client):
    assert client.get("/demo/stats").status_code == 200


def test_demo_stats_has_test_count(client):
    data = client.get("/demo/stats").json()
    assert "test_count" in data
    assert data["test_count"] > 0


def test_demo_stats_has_encryption_info(client):
    data = client.get("/demo/stats").json()
    assert "encryption" in data
    enc = data["encryption"]
    assert enc["algorithm"] == "AES-256-GCM"
    assert "key_derivation" in enc


def test_demo_stats_has_gemini_info(client):
    data = client.get("/demo/stats").json()
    assert "gemini" in data
    assert data["gemini"]["fallback_available"] is True


def test_demo_stats_has_dead_man_switch_info(client):
    data = client.get("/demo/stats").json()
    assert "dead_man_switch" in data
    assert data["dead_man_switch"]["threshold_days"] == 90


def test_demo_stats_has_dynamodb_info(client):
    data = client.get("/demo/stats").json()
    assert "dynamodb" in data
    assert "item_types" in data["dynamodb"]
    assert len(data["dynamodb"]["item_types"]) == 3
