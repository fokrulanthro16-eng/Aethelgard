from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReleaseRequest(BaseModel):
    token: str
    owner_email: str
    nominee_email: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    status: str  # PENDING | USED | EXPIRED
    used_at: Optional[datetime] = None


class ReleaseCreateResponse(BaseModel):
    token: str
    expires_at: datetime
    nominee_email: Optional[str] = None


class ReleaseValidationResponse(BaseModel):
    token: str
    owner_email: str
    nominee_email: Optional[str] = None
    expires_at: datetime
    status: str
    valid: bool


class ReleaseApprovalResponse(BaseModel):
    token: str
    owner_email: str
    approved: bool
    released_at: datetime
