
import logging
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import Lead, Outreach, Meeting
from app.schemas.lead import LeadCreate, LeadResponse
from app.schemas.meeting import MeetingCreate, MeetingResponse

from app.services.lead_generator import create_lead
from app.services.sample_leads import get_sample_leads
from app.services.lead_deduplicator import lead_exists
from app.services.ai_qualifier import AIQualifier
from app.services.qualification_parser import parse_qualification
from app.services.conversation_service import (
    save_message,
    get_conversation_history,
)
from app.services.chatbot import LeadChatbot
from app.services.outreach_service import OutreachService
from app.services.outreach_tracking import (
    create_outreach,
    get_outreach_history,
)
from app.services.telegram_service import TelegramService
from app.services.telegram_receiver import process_telegram_update
from app.services.google_calendar import create_calendar_event


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["Leads"])


# -----------------------------
# Request schemas
# -----------------------------

class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    message: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class OutreachCreate(BaseModel):
    channel: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class OutreachStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(Draft|Ready|Sent|Responded|Meeting Scheduled|Failed)$",
    )
    response: str | None = None


class TelegramChatIdUpdate(BaseModel):
    telegram_id: str = Field(..., min_length=1)


# -----------------------------
# 1. Create a lead
# POST /api/leads/
# -----------------------------

@router.post("/", response_model=LeadResponse)
def add_lead(
    lead_data: LeadCreate,
    db: Session = Depends(get_db),
):
    return create_lead(db=db, lead_data=lead_data)


# -----------------------------
# 2. List leads
# GET /api/leads/
# -----------------------------

@router.get("/")
def get_leads(db: Session = Depends(get_db)):
    return db.query(Lead).order_by(Lead.created_at.desc()).all()


# -----------------------------
# 3. Discover sample leads
# POST /api/leads/discover
# -----------------------------

@router.post("/discover")
def discover_leads(db: Session = Depends(get_db)):
    sample_leads = get_sample_leads()
    created = []
    skipped = 0

    for lead_data in sample_leads:
        # Match the lead_exists(db, name, company_name) signature.
        if lead_exists(
            db=db,
            name=lead_data.name,
            company_name=lead_data.company_name,
        ):
            skipped += 1
            continue

        try:
            lead = create_lead(db=db, lead_data=lead_data)
            created.append(
                {
                    "id": lead.id,
                    "name": lead.name,
                    "company_name": lead.company_name,
                    "category": lead.category,
                    "icp_score": lead.icp_score,
                }
            )
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to create a sample lead")
            raise HTTPException(
                status_code=500,
                detail="Failed to save a discovered sample lead.",
            ) from exc

    return {
        "message": "Sample lead discovery completed.",
        "created_count": len(created),
        "skipped_duplicates": skipped,
        "leads": created,
        "note": (
            "These are sample prospects for demonstration, "
            "not verified live leads."
        ),
    }


# -----------------------------
# 4. AI qualify a lead
# POST /api/leads/{lead_id}/qualify
# -----------------------------

@router.post("/{lead_id}/qualify")
def qualify_lead(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        # AIQualifier defines qualify_lead(), not qualify().
        raw_result = AIQualifier().qualify_lead(lead)
        parsed = parse_qualification(raw_result)

        lead.category = parsed.get("category", lead.category)
        lead.buying_intent = parsed.get("buying_intent")
        lead.pain_points = parsed.get("pain_points")
        lead.ai_summary = parsed.get("summary")
        lead.status = lead.category

        db.commit()
        db.refresh(lead)

        return {
            "lead_id": lead.id,
            "category": lead.category,
            "buying_intent": lead.buying_intent,
            "pain_points": lead.pain_points,
            "summary": lead.ai_summary,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Lead qualification failed for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail=f"Lead qualification failed: {exc}",
        ) from exc


# -----------------------------
# 5. Save a conversation message
# POST /api/leads/{lead_id}/messages
# -----------------------------

@router.post("/{lead_id}/messages")
def add_message(
    lead_id: int,
    message_data: MessageCreate,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    message = save_message(
        db=db,
        lead_id=lead_id,
        role=message_data.role,
        message=message_data.message,
    )

    return {
        "message": "Conversation message saved.",
        "id": message.id,
        "lead_id": lead_id,
    }


# -----------------------------
# 6. Get conversation history
# GET /api/leads/{lead_id}/messages
# -----------------------------

@router.get("/{lead_id}/messages")
def list_messages(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    history = get_conversation_history(db=db, lead_id=lead_id)

    return {
        "lead_id": lead_id,
        "message_count": len(history),
        "messages": history,
    }


# -----------------------------
# 7. Chat with the AI
# POST /api/leads/{lead_id}/chat
# -----------------------------

@router.post("/{lead_id}/chat")
def chat_with_lead(
    lead_id: int,
    chat_data: ChatRequest,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        save_message(
            db=db,
            lead_id=lead_id,
            role="user",
            message=chat_data.message,
        )

        reply = LeadChatbot().reply(db=db, lead=lead)

        return {
            "lead_id": lead_id,
            "user_message": chat_data.message,
            "ai_reply": reply,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("AI conversation failed for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail=f"AI conversation failed: {exc}",
        ) from exc


# -----------------------------
# 8. Preview an outreach message
# POST /api/leads/{lead_id}/outreach/preview
# -----------------------------

@router.post("/{lead_id}/outreach/preview")
def preview_outreach(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        message = OutreachService().generate_message(lead)

        return {
            "lead_id": lead_id,
            "channel": "telegram",
            "message": message,
            "status": "Draft",
        }

    except Exception as exc:
        logger.exception("Outreach generation failed for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail=f"Outreach generation failed: {exc}",
        ) from exc


# -----------------------------
# 9. Save an outreach draft
# POST /api/leads/{lead_id}/outreach
# -----------------------------

@router.post("/{lead_id}/outreach")
def add_outreach(
    lead_id: int,
    outreach_data: OutreachCreate,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    outreach = create_outreach(
        db=db,
        lead_id=lead_id,
        channel=outreach_data.channel,
        message=outreach_data.message,
    )

    return {
        "message": "Outreach draft saved.",
        "outreach_id": outreach.id,
        "lead_id": lead_id,
        "channel": outreach.channel,
        "status": outreach.status,
    }


# -----------------------------
# 10. Get outreach history
# GET /api/leads/{lead_id}/outreach
# -----------------------------

@router.get("/{lead_id}/outreach")
def list_outreach(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    history = get_outreach_history(db=db, lead_id=lead_id)

    return {
        "lead_id": lead_id,
        "outreach_count": len(history),
        "outreach": history,
    }


# -----------------------------
# 11. Update outreach status
# PATCH /api/leads/outreach/{outreach_id}
# -----------------------------

@router.patch("/outreach/{outreach_id}")
def update_outreach_status(
    outreach_id: int,
    update_data: OutreachStatusUpdate,
    db: Session = Depends(get_db),
):
    outreach = (
        db.query(Outreach)
        .filter(Outreach.id == outreach_id)
        .first()
    )

    if not outreach:
        raise HTTPException(
            status_code=404,
            detail="Outreach record not found.",
        )

    outreach.status = update_data.status

    if update_data.response is not None:
        outreach.response = update_data.response

    try:
        db.commit()
        db.refresh(outreach)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update outreach status.",
        ) from exc

    return {
        "message": "Outreach status updated.",
        "outreach_id": outreach.id,
        "status": outreach.status,
        "response": outreach.response,
    }


# -----------------------------
# 12. Send Telegram outreach
# POST /api/leads/{lead_id}/outreach/send-telegram
# -----------------------------

@router.post("/{lead_id}/outreach/send-telegram")
async def send_telegram_outreach(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if not lead.telegram_id:
        raise HTTPException(
            status_code=400,
            detail="This lead has no Telegram chat ID.",
        )

    try:
        message = OutreachService().generate_message(lead)

        telegram_result = await TelegramService().send_message(
            chat_id=lead.telegram_id,
            message=message,
        )

        outreach = create_outreach(
            db=db,
            lead_id=lead_id,
            channel="telegram",
            message=message,
        )

        outreach.status = "Sent"
        db.commit()
        db.refresh(outreach)

        return {
            "message": "Telegram outreach sent successfully.",
            "lead_id": lead_id,
            "outreach_id": outreach.id,
            "status": outreach.status,
            "telegram_message_id": telegram_result.get("message_id"),
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Telegram outreach failed for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail=f"Telegram outreach failed: {exc}",
        ) from exc


# -----------------------------
# 13. Telegram webhook
# POST /api/leads/telegram/webhook
# -----------------------------

@router.post("/telegram/webhook")
async def telegram_webhook(
    update: dict,
    db: Session = Depends(get_db),
):
    try:
        return await process_telegram_update(db=db, update=update)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to process Telegram update")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Telegram update: {exc}",
        ) from exc


# -----------------------------
# 14. Save a lead's Telegram chat ID
# PATCH /api/leads/{lead_id}/telegram-id
# -----------------------------

@router.patch("/{lead_id}/telegram-id")
def update_telegram_chat_id(
    lead_id: int,
    payload: TelegramChatIdUpdate,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found.",
        )

    telegram_id = payload.telegram_id.strip()

    if not telegram_id:
        raise HTTPException(
            status_code=422,
            detail="Telegram chat ID cannot be empty.",
        )

    try:
        lead.telegram_id = telegram_id
        db.commit()
        db.refresh(lead)
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to save Telegram chat ID for lead %s",
            lead_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save Telegram chat ID.",
        ) from exc

    return {
        "message": "Telegram chat ID saved successfully.",
        "lead_id": lead.id,
        "telegram_id": lead.telegram_id,
    }


# -----------------------------
# Meeting slot helper
# -----------------------------

def get_available_slot_times(
    db: Session,
    duration_minutes: int = 30,
) -> list[datetime]:
    timezone = ZoneInfo(settings.default_timezone)
    now = datetime.now(timezone).replace(tzinfo=None)
    available_slots = []

    existing_meetings = (
        db.query(Meeting)
        .filter(Meeting.status == "Scheduled")
        .all()
    )

    for day_offset in range(7):
        day = now.date() + timedelta(days=day_offset)

        # Monday to Friday only.
        if day.weekday() >= 5:
            continue

        # Half-hour start times, 10:00 AM to 4:30 PM.
        for minute_of_day in range(600, 991, 30):
            hour = minute_of_day // 60
            minute = minute_of_day % 60

            slot = datetime.combine(day, time(hour, minute))
            slot_end = slot + timedelta(minutes=duration_minutes)

            if slot <= now:
                continue

            conflict = any(
                slot < meeting.meeting_time
                + timedelta(minutes=meeting.duration_minutes)
                and slot_end > meeting.meeting_time
                for meeting in existing_meetings
            )

            if not conflict:
                available_slots.append(slot)

    return available_slots


# -----------------------------
# 15. List available meeting slots
# GET /api/leads/meetings/slots
# -----------------------------

@router.get("/meetings/slots")
def list_meeting_slots(
    db: Session = Depends(get_db),
):
    slots = get_available_slot_times(db=db)

    return {
        "timezone": settings.default_timezone,
        "duration_minutes": 30,
        "available_slots": [
            slot.isoformat() for slot in slots
        ],
    }


# -----------------------------
# 16. Book a meeting
# POST /api/leads/meetings/book
# -----------------------------

@router.post("/meetings/book", response_model=MeetingResponse)
async def book_meeting(
    meeting_data: MeetingCreate,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(
        Lead.id == meeting_data.lead_id
    ).first()

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found.",
        )

    if meeting_data.timezone != settings.default_timezone:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Use the configured timezone: "
                f"{settings.default_timezone}"
            ),
        )

    timezone = ZoneInfo(settings.default_timezone)
    meeting_time = meeting_data.meeting_time

    if meeting_time.tzinfo is not None:
        meeting_time = (
            meeting_time.astimezone(timezone)
            .replace(tzinfo=None)
        )

    now = datetime.now(timezone).replace(tzinfo=None)

    if meeting_time <= now:
        raise HTTPException(
            status_code=400,
            detail="Meeting time must be in the future.",
        )

    available_slots = get_available_slot_times(
        db=db,
        duration_minutes=meeting_data.duration_minutes,
    )

    if meeting_time not in available_slots:
        raise HTTPException(
            status_code=409,
            detail=(
                "This slot is unavailable. Fetch available slots "
                "and try again."
            ),
        )

    meeting = Meeting(
        lead_id=lead.id,
        meeting_title=meeting_data.meeting_title,
        meeting_time=meeting_time,
        duration_minutes=meeting_data.duration_minutes,
        timezone=settings.default_timezone,
        status="Scheduled",
        meeting_link=meeting_data.meeting_link,
        notes=meeting_data.notes,
    )

    try:
        db.add(meeting)
        lead.status = "Meeting Scheduled"
        db.commit()
        db.refresh(meeting)
    except Exception as exc:
        db.rollback()
        logger.exception("Meeting booking failed")
        raise HTTPException(
            status_code=500,
            detail=f"Meeting booking failed: {exc}",
        ) from exc

    # Create a Google Calendar event after saving the booking.
    # Calendar failure does not cancel the database booking.
    try:
        calendar_event = create_calendar_event(meeting)

        if (
            not meeting.meeting_link
            and calendar_event.get("html_link")
        ):
            meeting.meeting_link = calendar_event["html_link"]
            db.commit()
            db.refresh(meeting)

        logger.info(
            "Google Calendar event created for meeting %s "
            "(event ID: %s)",
            meeting.id,
            calendar_event.get("event_id"),
        )

    except Exception:
        db.rollback()
        logger.exception(
            "Google Calendar sync failed for meeting %s. "
            "The database booking remains saved.",
            meeting.id,
        )

    # Send meeting confirmation through Telegram.
    if not lead.telegram_id:
        logger.warning(
            "Meeting %s booked, but Telegram confirmation was skipped: "
            "lead %s has no Telegram chat ID.",
            meeting.id,
            lead.id,
        )
    else:
        confirmation_message = (
            f"Hi {lead.name or 'there'}, your meeting has been scheduled!\n\n"
            f"Meeting: {meeting.meeting_title}\n"
            f"Date and time: "
            f"{meeting.meeting_time.strftime('%d %b %Y, %I:%M %p')} "
            f"({meeting.timezone})\n"
            f"Duration: {meeting.duration_minutes} minutes\n"
        )

        if meeting.meeting_link:
            confirmation_message += (
                f"\nCalendar event: {meeting.meeting_link}"
            )

        try:
            telegram_result = await TelegramService().send_message(
                chat_id=lead.telegram_id,
                message=confirmation_message,
            )

            logger.info(
                "Telegram confirmation sent for meeting %s; "
                "message ID: %s",
                meeting.id,
                telegram_result.get("message_id"),
            )

        except Exception:
            logger.exception(
                "Meeting %s was booked, but Telegram confirmation failed.",
                meeting.id,
            )

    return meeting


# -----------------------------
# 17. Retrieve a meeting
# GET /api/leads/meetings/{meeting_id}
# -----------------------------

@router.get(
    "/meetings/{meeting_id}",
    response_model=MeetingResponse,
)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id
    ).first()

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    return meeting