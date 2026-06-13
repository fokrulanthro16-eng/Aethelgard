"""
Tests for the /users and /users/{email}/check-in endpoints.

All DynamoDB calls are intercepted by moto via the `client` fixture in conftest.py.
No real AWS credentials or network access are required.
"""

# ── Create user ───────────────────────────────────────────────────────────────


def test_create_user_returns_201(client):
    response = client.post("/users", json={"email": "alice@example.com"})
    assert response.status_code == 201


def test_create_user_response_schema(client):
    response = client.post("/users", json={"email": "alice@example.com"})
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["status"] == "ACTIVE"
    assert data["dead_man_switch_days"] == 90
    assert "PK" in data
    assert "SK" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "last_checkin_at" in data


def test_create_user_with_nominee(client):
    response = client.post(
        "/users",
        json={"email": "bob@example.com", "nominee_email": "charlie@example.com"},
    )
    assert response.status_code == 201
    assert response.json()["nominee_email"] == "charlie@example.com"


def test_create_user_without_nominee(client):
    response = client.post("/users", json={"email": "dana@example.com"})
    assert response.status_code == 201
    assert response.json()["nominee_email"] is None


def test_create_duplicate_user_returns_409(client):
    client.post("/users", json={"email": "eve@example.com"})
    response = client.post("/users", json={"email": "eve@example.com"})
    assert response.status_code == 409


def test_create_user_invalid_email_returns_422(client):
    response = client.post("/users", json={"email": "not-an-email"})
    assert response.status_code == 422


# ── Get user ──────────────────────────────────────────────────────────────────


def test_get_existing_user_returns_200(client):
    client.post("/users", json={"email": "frank@example.com"})
    response = client.get("/users/frank@example.com")
    assert response.status_code == 200


def test_get_existing_user_response_schema(client):
    client.post("/users", json={"email": "grace@example.com"})
    data = client.get("/users/grace@example.com").json()
    assert data["email"] == "grace@example.com"
    assert data["status"] == "ACTIVE"


def test_get_nonexistent_user_returns_404(client):
    response = client.get("/users/nobody@example.com")
    assert response.status_code == 404


# ── Check-in ──────────────────────────────────────────────────────────────────


def test_checkin_returns_200(client):
    client.post("/users", json={"email": "henry@example.com"})
    response = client.post("/users/henry@example.com/check-in")
    assert response.status_code == 200


def test_checkin_response_schema(client):
    client.post("/users", json={"email": "iris@example.com"})
    data = client.post("/users/iris@example.com/check-in").json()
    assert data["email"] == "iris@example.com"
    assert "last_checkin_at" in data
    assert "next_check_due" in data
    assert "message" in data


def test_checkin_message_content(client):
    client.post("/users", json={"email": "jack@example.com"})
    data = client.post("/users/jack@example.com/check-in").json()
    assert "Check-in recorded" in data["message"]


def test_checkin_next_due_is_90_days_ahead(client):
    from datetime import datetime

    client.post("/users", json={"email": "kate@example.com"})
    data = client.post("/users/kate@example.com/check-in").json()

    last = datetime.fromisoformat(data["last_checkin_at"])
    nxt = datetime.fromisoformat(data["next_check_due"])
    delta_days = (nxt - last).days
    assert delta_days == 90


def test_checkin_updates_user_record(client):
    client.post("/users", json={"email": "leo@example.com"})
    checkin_data = client.post("/users/leo@example.com/check-in").json()
    user_data = client.get("/users/leo@example.com").json()
    assert user_data["last_checkin_at"] == checkin_data["last_checkin_at"]


def test_checkin_nonexistent_user_returns_404(client):
    response = client.post("/users/ghost@example.com/check-in")
    assert response.status_code == 404


# ── Admin init-db ─────────────────────────────────────────────────────────────


def test_init_db_table_already_exists(client):
    # Table is pre-created by the mock_dynamodb fixture;
    # calling init-db should return without error (idempotent).
    response = client.post("/admin/init-db")
    assert response.status_code == 200
    data = response.json()
    assert data["created"] is False
