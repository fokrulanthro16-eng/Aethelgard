from datetime import datetime

from pydantic import BaseModel


class FamilyGuideResponse(BaseModel):
    generated_at: datetime
    guide: str
    source: str  # "gemini" | "fallback"
