
import logging

from sqlalchemy.orm import Session

from app.database.models import Lead
from app.services.conversation_service import save_message
from app.services.chatbot import LeadChatbot
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


async def process_telegram_update(db: Session, update: dict) -> dict:
    message = update.get("message")

    if not message:
        logger.info("Telegram update received without a message.")
        return {"processed": False, "reason": "No message in update"}

    chat = message.get("chat", {})
    text = message.get("text")

    if not chat.get("id") or not text:
        logger.info("Telegram message has no chat ID or text.")
        return {"processed": False, "reason": "No chat ID or text"}

    chat_id = str(chat["id"])

    # Log the chat ID so it can be saved to a lead.
    logger.info("Telegram chat ID received: %s", chat_id)

    lead = (
        db.query(Lead)
        .filter(Lead.telegram_id == chat_id)
        .first()
    )

    if not lead:
        logger.info(
            "No lead is linked to Telegram chat ID %s",
            chat_id,
        )
        return {
            "processed": False,
            "reason": "No matching lead",
            "chat_id": chat_id,
        }

    save_message(
        db=db,
        lead_id=lead.id,
        role="user",
        message=text,
    )

    try:
        reply = LeadChatbot().reply(db=db, lead=lead)

        await TelegramService().send_message(
            chat_id=chat_id,
            message=reply,
        )

    except Exception:
        db.rollback()
        logger.exception("Failed to process Telegram message.")
        raise

    return {
        "processed": True,
        "lead_id": lead.id,
        "reply_sent": True,
        "ai_reply": reply,
    }