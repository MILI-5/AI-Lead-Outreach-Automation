from sqlalchemy.orm import Session

from app.database.models import Lead
from app.schemas.lead import LeadCreate
from app.services.lead_scorer import (
    calculate_icp_score,
    categorize_lead,
)


def create_lead(
    db: Session,
    lead_data: LeadCreate
) -> Lead:
    """
    Create and score a lead.
    """

    # Create database object
    lead = Lead(
        name=lead_data.name,
        designation=lead_data.designation,
        company_name=lead_data.company_name,
        company_website=lead_data.company_website,
        linkedin_url=lead_data.linkedin_url,
        instagram_url=lead_data.instagram_url,
        telegram_id=lead_data.telegram_id,
        email=lead_data.email,
        industry=lead_data.industry,
        location=lead_data.location,
        business_requirement=lead_data.business_requirement,
        company_size=lead_data.company_size,
        source=lead_data.source,
    )

    # Calculate ICP score
    score = calculate_icp_score(lead)

    # Categorize lead
    category = categorize_lead(score)

    lead.icp_score = score
    lead.category = category
    lead.status = "New"

    # Save to database
    db.add(lead)
    db.commit()
    db.refresh(lead)

    return lead