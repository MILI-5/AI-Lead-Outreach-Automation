
from sqlalchemy.orm import Session

from app.database.models import Conversation


def save_message(
    db: Session,
    lead_id: int,
    role: str,
    message: str
) -> Conversation:
    conversation = Conversation(
        lead_id=lead_id,
        role=role,
        message=message
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def get_conversation_history(
    db: Session,
    lead_id: int
) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.lead_id == lead_id)
        .order_by(Conversation.created_at.asc(), Conversation.id.asc())
        .all()
    )