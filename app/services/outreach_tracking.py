
from sqlalchemy.orm import Session

from app.database.models import Outreach


def create_outreach(
    db: Session,
    lead_id: int,
    channel: str,
    message: str,
) -> Outreach:
    outreach = Outreach(
        lead_id=lead_id,
        channel=channel,
        message=message,
        status="Draft",
    )
    db.add(outreach)
    db.commit()
    db.refresh(outreach)
    return outreach


def get_outreach_history(db: Session, lead_id: int) -> list[Outreach]:
    return (
        db.query(Outreach)
        .filter(Outreach.lead_id == lead_id)
        .order_by(Outreach.created_at.desc(), Outreach.id.desc())
        .all()
    )