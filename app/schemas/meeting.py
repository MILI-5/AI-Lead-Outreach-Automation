from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class MeetingCreate(BaseModel):
    lead_id: int = Field(..., gt=0)
    meeting_time: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)
    timezone: str = "Asia/Kolkata"
    meeting_title: str = "Lead Discovery Meeting"
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


class MeetingResponse(BaseModel):
    id: int
    lead_id: int
    meeting_title: str
    meeting_time: datetime
    duration_minutes: int
    timezone: str
    status: str
    meeting_link: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)