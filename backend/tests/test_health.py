"""
Tests for the /health endpoint and basic FastAPI wiring.
These tests run without AWS credentials — no DynamoDB calls are made.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_schema():
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "environment" in data


def test_health_service_name():
    response = client.get("/health")
    data = response.json()
    assert data["service"] == "Aethelgard API"


def test_docs_available():
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json_available():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Aethelgard API"
