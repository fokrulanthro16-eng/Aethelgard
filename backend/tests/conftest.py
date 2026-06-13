"""
Shared pytest fixtures.

DynamoDB is mocked with moto — no real AWS credentials or network access required.
"""

import os

# Fake AWS credentials so moto intercepts all boto3 calls cleanly.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

# Force tests to use moto's in-process mock, NOT any local HTTP endpoint.
# Without this, a DYNAMODB_ENDPOINT_URL value in backend/.env would be picked
# up by pydantic-settings and passed to boto3, routing calls to the HTTP server
# instead of the in-process mock and breaking test isolation.
os.environ["DYNAMODB_ENDPOINT_URL"] = ""

# Encryption: use local mode with a fixed test master key.
# Never use this key value outside of automated tests.
os.environ.setdefault("ENCRYPTION_MODE", "local")
os.environ.setdefault("LOCAL_MASTER_KEY", "test-master-key-do-not-use-in-production-32b!")

import boto3
import pytest
from moto import mock_aws

from app.core.config import settings


@pytest.fixture()
def mock_dynamodb():
    """Activate the moto DynamoDB mock and provision the vault table."""
    with mock_aws():
        db = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
        db.create_table(
            TableName=settings.DYNAMODB_TABLE_NAME,
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture()
def client(mock_dynamodb):
    """FastAPI TestClient with a freshly mocked DynamoDB table per test."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c
