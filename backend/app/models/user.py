from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    nominee_email: Optional[EmailStr] = None


class UserMetadata(BaseModel):
    PK: str
    SK: str
    email: EmailStr
    nominee_email: Optional[EmailStr] = None
    created_at: datetime
    updated_at: datetime
    last_checkin_at: datetime
    next_check_due_at: Optional[datetime] = None
    dead_man_switch_days: int = Field(default=90, ge=1)
    status: str = "ACTIVE"
    release_candidate_at: Optional[datetime] = None
    released_at: Optional[datetime] = None


class CheckInResponse(BaseModel):
    message: str
    email: EmailStr
    last_checkin_at: datetime
    next_check_due: datetime
