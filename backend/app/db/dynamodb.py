"""
DynamoDB access layer for Aethelgard_Vault.

Table design (single-table):
  PK = USER#<email>   SK = METADATA        → user record
  PK = USER#<email>   SK = VAULT#<uuid>    → encrypted vault entry
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.core.config import settings


# ── Resource / table helpers ──────────────────────────────────────────────────

def get_dynamodb_resource() -> Any:
    kwargs: dict[str, Any] = {"region_name": settings.AWS_REGION}
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
    if settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.resource("dynamodb", **kwargs)


def get_vault_table() -> Any:
    db = get_dynamodb_resource()
    return db.Table(settings.DYNAMODB_TABLE_NAME)


# ── Table bootstrap ───────────────────────────────────────────────────────────

def create_vault_table_if_not_exists() -> dict[str, Any]:
    """
    Creates the Aethelgard_Vault table with PAY_PER_REQUEST billing.
    Safe to call repeatedly — returns existing table info if already present.
    """
    db = get_dynamodb_resource()
    try:
        table = db.create_table(
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
        table.wait_until_exists()
        return {"created": True, "table_name": settings.DYNAMODB_TABLE_NAME}
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            return {"created": False, "table_name": settings.DYNAMODB_TABLE_NAME}
        raise


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pk(email: str) -> str:
    return f"USER#{email.lower().strip()}"


def put_user_metadata(
    email: str,
    nominee_email: str | None = None,
) -> dict[str, Any]:
    """
    Creates a new user metadata item.
    Raises ValueError if the user already exists.
    """
    table = get_vault_table()
    pk = _pk(email)
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    next_check_due_at = (now_dt + timedelta(days=settings.DEAD_MAN_SWITCH_DAYS)).isoformat()

    item: dict[str, Any] = {
        "PK": pk,
        "SK": "METADATA",
        "email": email.lower().strip(),
        "nominee_email": nominee_email,
        "created_at": now,
        "updated_at": now,
        "last_checkin_at": now,
        "next_check_due_at": next_check_due_at,
        "dead_man_switch_days": settings.DEAD_MAN_SWITCH_DAYS,
        "status": "ACTIVE",
    }

    try:
        table.put_item(
            Item=item,
            # Prevent overwriting an existing user
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"User {email} already exists.")
        raise

    return item


def get_user_metadata(email: str) -> dict[str, Any] | None:
    """Returns the user metadata item or None if not found."""
    table = get_vault_table()
    response = table.get_item(
        Key={"PK": _pk(email), "SK": "METADATA"}
    )
    return response.get("Item")


def update_last_checkin(email: str) -> dict[str, Any]:
    """
    Stamps last_checkin_at, next_check_due_at, and updated_at to UTC now.
    Resets status to ACTIVE (cancels any pending PENDING_RELEASE).
    Raises ValueError if the user does not exist.
    """
    table = get_vault_table()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    next_check_due_at = (now_dt + timedelta(days=settings.DEAD_MAN_SWITCH_DAYS)).isoformat()

    try:
        response = table.update_item(
            Key={"PK": _pk(email), "SK": "METADATA"},
            UpdateExpression=(
                "SET last_checkin_at = :now, updated_at = :now, "
                "next_check_due_at = :next_due, #s = :active"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":now": now,
                ":next_due": next_check_due_at,
                ":active": "ACTIVE",
            },
            ConditionExpression="attribute_exists(PK)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"User {email} does not exist.")
        raise

    return response["Attributes"]


# ── Vault entry helpers ───────────────────────────────────────────────────────

def _vault_sk(entry_id: str) -> str:
    return f"VAULT#{entry_id}"


def put_encrypted_vault_entry(email: str, entry: dict[str, Any]) -> dict[str, Any]:
    """
    Persists a vault entry whose sensitive fields are already encrypted.
    `entry` must contain: entry_type, title, sensitive_data (encrypted dict).
    `entry` may contain: notes (encrypted dict or None).
    Returns the full item as stored.
    """
    table = get_vault_table()
    entry_id = str(uuid.uuid4())
    now = _now_iso()

    item: dict[str, Any] = {
        "PK": _pk(email),
        "SK": _vault_sk(entry_id),
        "entry_id": entry_id,
        "entry_type": entry["entry_type"],
        "title": entry["title"],
        "sensitive_data": entry["sensitive_data"],  # encrypted payload dict
        "notes": entry.get("notes"),               # encrypted payload dict or None
        "created_at": now,
        "updated_at": now,
    }

    table.put_item(Item=item)
    return item


def list_vault_entries(email: str) -> list[dict[str, Any]]:
    """Returns all vault entries for a user (metadata only — does NOT decrypt)."""
    table = get_vault_table()
    response = table.query(
        KeyConditionExpression=Key("PK").eq(_pk(email)) & Key("SK").begins_with("VAULT#")
    )
    return response.get("Items", [])


def get_vault_entry(email: str, entry_id: str) -> dict[str, Any] | None:
    """Returns a single vault entry (still encrypted) or None if not found."""
    table = get_vault_table()
    response = table.get_item(
        Key={"PK": _pk(email), "SK": _vault_sk(entry_id)}
    )
    return response.get("Item")


def delete_vault_entry(email: str, entry_id: str) -> bool:
    """
    Deletes a vault entry.
    Returns True if the entry existed and was deleted, False if not found.
    """
    table = get_vault_table()
    try:
        table.delete_item(
            Key={"PK": _pk(email), "SK": _vault_sk(entry_id)},
            ConditionExpression="attribute_exists(PK)",
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# ── Demo helpers ──────────────────────────────────────────────────────────────

def delete_all_user_items(email: str) -> int:
    """
    Deletes all DynamoDB items in the USER#{email} partition (METADATA + all VAULT entries).
    Returns the number of items deleted.
    Used by the demo seed to reset the demo account on each call.
    """
    table = get_vault_table()
    response = table.query(
        KeyConditionExpression=Key("PK").eq(_pk(email))
    )
    items = response.get("Items", [])
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
    return len(items)


# ── Dead Man's Switch helpers ─────────────────────────────────────────────────

def mark_pending_release(email: str) -> dict[str, Any]:
    """
    Transitions a user from ACTIVE → PENDING_RELEASE.
    Raises ValueError if the user does not exist or is not ACTIVE.
    """
    table = get_vault_table()
    now = _now_iso()
    try:
        response = table.update_item(
            Key={"PK": _pk(email), "SK": "METADATA"},
            UpdateExpression="SET #s = :pending, release_candidate_at = :now, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":pending": "PENDING_RELEASE",
                ":now": now,
                ":active": "ACTIVE",
            },
            ConditionExpression="attribute_exists(PK) AND #s = :active",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(f"User {email} does not exist or is not ACTIVE.")
        raise
    return response["Attributes"]


def scan_all_user_metadata() -> list[dict[str, Any]]:
    """
    Returns every METADATA item in the table (one per user).

    TODO (production): Replace with a GSI query on SK="METADATA" to avoid
    scanning all items (vault entries included). At scale a full-table scan
    is expensive and slow.
    """
    table = get_vault_table()
    response = table.scan(FilterExpression=Attr("SK").eq("METADATA"))
    return response.get("Items", [])


# ── Release request helpers ───────────────────────────────────────────────────

def _release_pk(token: str) -> str:
    return f"RELEASE#{token}"


def put_release_request(
    token: str,
    owner_email: str,
    nominee_email: str | None,
    expires_at: str,
) -> dict[str, Any]:
    """Persists a new release request. Overwrites an existing item for the same token."""
    table = get_vault_table()
    now = _now_iso()
    item: dict[str, Any] = {
        "PK": _release_pk(token),
        "SK": "REQUEST",
        "token": token,
        "owner_email": owner_email.lower().strip(),
        "nominee_email": nominee_email,
        "created_at": now,
        "expires_at": expires_at,
        "status": "PENDING",
    }
    table.put_item(Item=item)
    return item


def get_release_request(token: str) -> dict[str, Any] | None:
    """Returns the release request item or None if not found."""
    table = get_vault_table()
    response = table.get_item(Key={"PK": _release_pk(token), "SK": "REQUEST"})
    return response.get("Item")


def mark_release_used(token: str, used_at: str) -> dict[str, Any]:
    """
    Transitions a release request PENDING → USED.
    Raises ValueError if the token is not in PENDING status.
    """
    table = get_vault_table()
    try:
        response = table.update_item(
            Key={"PK": _release_pk(token), "SK": "REQUEST"},
            UpdateExpression="SET #s = :used, used_at = :used_at",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":used": "USED",
                ":used_at": used_at,
                ":pending": "PENDING",
            },
            ConditionExpression="attribute_exists(PK) AND #s = :pending",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError("Release token is not in PENDING status.")
        raise
    return response["Attributes"]


def mark_release_expired(token: str) -> dict[str, Any]:
    """Marks a release request as EXPIRED. Raises ValueError if not found."""
    table = get_vault_table()
    try:
        response = table.update_item(
            Key={"PK": _release_pk(token), "SK": "REQUEST"},
            UpdateExpression="SET #s = :expired",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":expired": "EXPIRED"},
            ConditionExpression="attribute_exists(PK)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError("Release token not found.")
        raise
    return response["Attributes"]


def mark_released(email: str) -> dict[str, Any]:
    """
    Transitions a user from PENDING_RELEASE → RELEASED.
    Raises ValueError if the user does not exist or is not PENDING_RELEASE.

    TODO (production): Pair this with mark_release_used in a DynamoDB
    TransactWriteItems call so both updates are atomic.
    """
    table = get_vault_table()
    now = _now_iso()
    try:
        response = table.update_item(
            Key={"PK": _pk(email), "SK": "METADATA"},
            UpdateExpression="SET #s = :released, released_at = :now, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":released": "RELEASED",
                ":now": now,
                ":pending": "PENDING_RELEASE",
            },
            ConditionExpression="attribute_exists(PK) AND #s = :pending",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError(
                f"User {email} does not exist or is not in PENDING_RELEASE status."
            )
        raise
    return response["Attributes"]

