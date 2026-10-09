from typing import Optional

from pydantic import BaseModel, Field


class LeadCreate(BaseModel):
    """
    Data required to create a new lead.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255
    )

    designation: Optional[str] = None

    company_name: Optional[str] = None

    company_website: Optional[str] = None

    linkedin_url: Optional[str] = None

    instagram_url: Optional[str] = None

    telegram_id: Optional[str] = None

    email: Optional[str] = None

    industry: Optional[str] = None

    location: Optional[str] = None

    business_requirement: Optional[str] = None

    company_size: Optional[int] = None

    source: Optional[str] = "manual"


class LeadResponse(LeadCreate):
    """
    Response returned by the API after processing a lead.
    """

    id: int

    icp_score: int

    category: str

    status: str

    pain_points: Optional[str] = None

    ai_summary: Optional[str] = None

    buying_intent: Optional[str] = None

    class Config:
        from_attributes = True