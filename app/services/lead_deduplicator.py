from sqlalchemy.orm import Session

from app.database.models import Lead


def normalize(value: str | None) -> str:
    """
    Normalize text for comparison.
    """

    if not value:
        return ""

    return value.lower().strip()


def lead_exists(
    db: Session,
    name: str | None,
    company_name: str | None
) -> bool:
    """
    Check whether a similar lead already exists.
    """

    if not name or not company_name:
        return False

    existing_leads = (
        db.query(Lead)
        .filter(
            Lead.company_name.isnot(None)
        )
        .all()
    )

    normalized_name = normalize(name)
    normalized_company = normalize(company_name)

    for lead in existing_leads:

        existing_name = normalize(
            lead.name
        )

        existing_company = normalize(
            lead.company_name
        )

        if (
            existing_name == normalized_name
            and
            existing_company == normalized_company
        ):
            return True

    return False