from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


ENTRY_TYPES = {"message", "note", "credentials", "document"}


class VaultEntryCreate(BaseModel):
    """Payload the client sends when creating a vault entry.
    sensitive_data and notes are plaintext here — the API layer encrypts them
    before anything touches DynamoDB."""
    entry_type: str = Field(..., description="message | note | credentials | document")
    title: str = Field(..., min_length=1, max_length=200)
    sensitive_data: str = Field(..., min_length=1, description="Plaintext secret content")
    notes: Optional[str] = Field(default=None, description="Optional plaintext notes")


class VaultEntryResponse(BaseModel):
    """Metadata-only response returned by the list and create endpoints.
    Encrypted fields (sensitive_data, notes) are intentionally omitted."""
    entry_id: str
    entry_type: str
    title: str
    created_at: datetime
    updated_at: datetime


class VaultEntryDecrypted(BaseModel):
    """Full decrypted entry returned by the single-GET endpoint.
    TODO (before production): this endpoint must be protected by auth so only
    the vault owner can decrypt their own entries."""
    entry_id: str
    entry_type: str
    title: str
    sensitive_data: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
