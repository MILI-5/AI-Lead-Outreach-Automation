from typing import Optional

from pydantic import BaseModel, Field


class LeadSearchRequest(BaseModel):
    """
    Parameters used to search for potential leads.
    """

    industry: str = Field(
        ...,
        description="Target industry"
    )

    designation: str = Field(
        ...,
        description="Target decision-maker designation"
    )

    location: str = Field(
        ...,
        description="Target location"
    )

    business_requirement: str = Field(
        ...,
        description="Problem or requirement we want to target"
    )

    company_size: Optional[str] = Field(
        default=None,
        description="Target company size"
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=25
    )


class DiscoveredLead(BaseModel):
    """
    Structured lead returned by the AI extraction layer.
    """

    name: Optional[str] = None

    designation: Optional[str] = None

    company_name: Optional[str] = None

    company_website: Optional[str] = None

    linkedin_url: Optional[str] = None

    instagram_url: Optional[str] = None

    industry: Optional[str] = None

    location: Optional[str] = None

    business_requirement: Optional[str] = None

    company_size: Optional[int] = None

    source: str = "google"

    source_url: Optional[str] = None

    discovery_reason: Optional[str] = None


class LeadDiscoveryResponse(BaseModel):
    """
    Final response returned by the discovery API.
    """

    search_query: str

    leads_found: int

    leads_created: int

    leads_skipped: int

    leads: list[DiscoveredLead]