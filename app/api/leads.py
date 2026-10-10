
import logging
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import Lead, Outreach, Meeting
from app.schemas.lead import LeadCreate, LeadResponse
from app.schemas.meeting import MeetingCreate, MeetingResponse

from app.services.lead_generator import create_lead
from app.services.free_company_discovery import discover_companies
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
# -----------------------------

@router.post("/", response_model=LeadResponse)
def add_lead(
    lead_data: LeadCreate,
    db: Session = Depends(get_db),
):
    return create_lead(db=db, lead_data=lead_data)


# -----------------------------
# 2. List leads
# -----------------------------

@router.get("/")
def get_leads(db: Session = Depends(get_db)):
    return db.query(Lead).order_by(Lead.created_at.desc()).all()


# -----------------------------
# 3. Discover company candidates
# -----------------------------

@router.post("/discover")
def discover_leads(db: Session = Depends(get_db)):
    """Discover unverified company candidates from Hacker News."""
    try:
        candidates = discover_companies(limit=10)
    except Exception as exc:
        logger.exception("Free company discovery failed")
        raise HTTPException(
            status_code=502,
            detail="Company discovery failed. Please try again later.",
        ) from exc

    created = []
    skipped = 0
    failed = 0

    for candidate in candidates:
        company_name = (candidate.get("company_name") or "").strip()
        website = (candidate.get("company_website") or "").strip().rstrip("/")

        if (
            not company_name
            or not website
            or not website.startswith(("https://", "http://"))
        ):
            skipped += 1
            continue

        existing = (
            db.query(Lead)
            .filter(Lead.company_website == website)
            .first()
        )
        if existing:
            skipped += 1
            continue

        lead_data = LeadCreate(
            name=candidate.get("name") or "Contact not identified",
            designation=None,
            company_name=company_name[:255],
            company_website=website[:500],
            linkedin_url=None,
            instagram_url=None,
            telegram_id=None,
            email=None,
            industry=candidate.get("industry") or "AI / Technology",
            location=None,
            business_requirement=(
                "Potential prospect discovered from a public discussion. "
                "Verify the company, website, decision-maker, and ICP fit "
                "before contacting the prospect."
            ),
            company_size=None,
            source="hacker_news",
        )

        try:
            lead = create_lead(db=db, lead_data=lead_data)
            created.append({
                "id": lead.id,
                "name": lead.name,
                "company_name": lead.company_name,
                "company_website": lead.company_website,
                "industry": lead.industry,
                "category": lead.category,
                "icp_score": lead.icp_score,
                "status": lead.status,
                "source": lead.source,
                "source_url": candidate.get("source_url"),
                "verification_status": (
                    candidate.get("verification_status") or "Unverified"
                ),
            })
        except Exception:
            db.rollback()
            failed += 1
            logger.exception(
                "Failed to save discovered candidate: %s",
                company_name,
            )

    return {
        "message": "Free company discovery completed.",
        "discovered_count": len(candidates),
        "created_count": len(created),
        "skipped_duplicates_or_invalid": skipped,
        "failed_count": failed,
        "leads": created,
        "note": (
            "Discovery results are unverified candidates, not confirmed "
            "prospects. Verify company details and contact information "
            "before outreach. Source URLs are not persisted in the "
            "current Lead model."
        ),
    }


# -----------------------------
# 4. AI qualify a lead
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
        raw_result = AIQualifier().qualify_lead(lead)
        parsed = parse_qualification(raw_result)

        # Qualification fields and workflow status are separate.
        # Never set lead.status from lead.category here.
        category = parsed.get("category")
        if category:
            allowed_categories = {
                "Qualified",
                "Potential",
                "Not Qualified",
            }
            if category not in allowed_categories:
                raise ValueError(
                    f"Unexpected qualification category: {category}"
                )
            lead.category = category

        if "buying_intent" in parsed:
            lead.buying_intent = parsed["buying_intent"]

        if "pain_points" in parsed:
            lead.pain_points = parsed["pain_points"]

        if "summary" in parsed:
            lead.ai_summary = parsed["summary"]

        db.commit()
        db.refresh(lead)

        return {
            "lead_id": lead.id,
            "category": lead.category,
            "status": lead.status,
            "buying_intent": lead.buying_intent,
            "pain_points": lead.pain_points,
            "summary": lead.ai_summary,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Qualification failed for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail="Lead qualification failed. Check the backend logs.",
        ) from exc


# -----------------------------
# 5. Save a conversation message
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

    try:
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
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to save message for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to save conversation message.",
        ) from exc


# -----------------------------
# 6. Get conversation history
# -----------------------------

@router.get("/{lead_id}/messages")
def list_messages(
    lead_id: int,
    db: Session = Depends(get_db),
):
    if not db.query(Lead.id).filter(Lead.id == lead_id).first():
        raise HTTPException(status_code=404, detail="Lead not found.")

    history = get_conversation_history(db=db, lead_id=lead_id)
    return {
        "lead_id": lead_id,
        "message_count": len(history),
        "messages": history,
    }


# -----------------------------
# 7. Chat with the AI
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

        save_message(
            db=db,
            lead_id=lead_id,
            role="assistant",
            message=reply,
        )

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
            detail="AI conversation failed. Check the backend logs.",
        ) from exc


# -----------------------------
# 8. Preview outreach
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
            detail="Outreach generation failed. Check the backend logs.",
        ) from exc


# -----------------------------
# 9. Save outreach draft
# -----------------------------

@router.post("/{lead_id}/outreach")
def add_outreach(
    lead_id: int,
    outreach_data: OutreachCreate,
    db: Session = Depends(get_db),
):
    if not db.query(Lead.id).filter(Lead.id == lead_id).first():
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
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
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to save outreach for lead %s", lead_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to save outreach draft.",
        ) from exc


# -----------------------------
# 10. Get outreach history
# -----------------------------

@router.get("/{lead_id}/outreach")
def list_outreach(
    lead_id: int,
    db: Session = Depends(get_db),
):
    if not db.query(Lead.id).filter(Lead.id == lead_id).first():
        raise HTTPException(status_code=404, detail="Lead not found.")

    history = get_outreach_history(db=db, lead_id=lead_id)
    return {
        "lead_id": lead_id,
        "outreach_count": len(history),
        "outreach": history,
    }


# -----------------------------
# 11. Update outreach status
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

    try:
        outreach.status = update_data.status
        if update_data.response is not None:
            outreach.response = update_data.response

        db.commit()
        db.refresh(outreach)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to update outreach %s", outreach_id)
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
            detail="Telegram outreach failed. Check the backend logs.",
        ) from exc


# -----------------------------
# 13. Telegram webhook
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
            detail="Failed to process Telegram update.",
        ) from exc


# -----------------------------
# 14. Save Telegram chat ID
# -----------------------------

@router.patch("/{lead_id}/telegram-id")
def update_telegram_chat_id(
    lead_id: int,
    payload: TelegramChatIdUpdate,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

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
        logger.exception("Failed to save Telegram chat ID for lead %s", lead_id)
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
        if day.weekday() >= 5:
            continue

        for minute_of_day in range(600, 991, 30):
            hour, minute = divmod(minute_of_day, 60)
            slot = datetime.combine(day, time(hour, minute))
            slot_end = slot + timedelta(minutes=duration_minutes)

            if slot <= now:
                continue

            conflict = False
            for meeting in existing_meetings:
                existing_start = meeting.meeting_time

                if existing_start.tzinfo is not None:
                    existing_start = (
                        existing_start.astimezone(timezone)
                        .replace(tzinfo=None)
                    )

                existing_end = existing_start + timedelta(
                    minutes=meeting.duration_minutes
                )

                if slot < existing_end and slot_end > existing_start:
                    conflict = True
                    break

            if not conflict:
                available_slots.append(slot)

    return available_slots


# -----------------------------
# 15. List meeting slots
# -----------------------------

@router.get("/meetings/slots")
def list_meeting_slots(db: Session = Depends(get_db)):
    slots = get_available_slot_times(db=db)
    return {
        "timezone": settings.default_timezone,
        "duration_minutes": 30,
        "available_slots": [slot.isoformat() for slot in slots],
    }


# -----------------------------
# 16. Book a meeting
# -----------------------------

@router.post("/meetings/book", response_model=MeetingResponse)
async def book_meeting(
    meeting_data: MeetingCreate,
    db: Session = Depends(get_db),
):
    lead = (
        db.query(Lead)
        .filter(Lead.id == meeting_data.lead_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if meeting_data.timezone != settings.default_timezone:
        raise HTTPException(
            status_code=400,
            detail=f"Use the configured timezone: {settings.default_timezone}",
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
            detail="This slot is unavailable. Fetch available slots and try again.",
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
            detail="Meeting booking failed.",
        ) from exc

    # Calendar integration is best-effort; keep the database booking.
    try:
        calendar_event = create_calendar_event(meeting)
        if (
            not meeting.meeting_link
            and calendar_event
            and calendar_event.get("html_link")
        ):
            meeting.meeting_link = calendar_event["html_link"]
            db.commit()
            db.refresh(meeting)
    except Exception:
        db.rollback()
        logger.exception(
            "Calendar sync failed for meeting %s; local booking remains saved.",
            meeting.id,
        )

    # Send Telegram confirmation only if a chat ID is available.
    if lead.telegram_id:
        confirmation = (
            f"Hi {lead.name or 'there'}, your meeting has been scheduled!\n\n"
            f"Meeting: {meeting.meeting_title}\n"
            f"Date and time: "
            f"{meeting.meeting_time.strftime('%d %b %Y, %I:%M %p')} "
            f"({meeting.timezone})\n"
            f"Duration: {meeting.duration_minutes} minutes\n"
        )
        if meeting.meeting_link:
            confirmation += f"\nCalendar event: {meeting.meeting_link}"

        try:
            await TelegramService().send_message(
                chat_id=lead.telegram_id,
                message=confirmation,
            )
        except Exception:
            logger.exception(
                "Meeting %s booked, but Telegram confirmation failed.",
                meeting.id,
            )

    return meeting


# -----------------------------
# 17. Retrieve a meeting
# -----------------------------

@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return meeting


# -----------------------------
# 18. List all meetings
# -----------------------------

@router.get("/meetings")
def list_all_meetings(db: Session = Depends(get_db)):
    scheduled_count = (
        db.query(func.count(Meeting.id))
        .filter(Meeting.status == "Scheduled")
        .scalar()
        or 0
    )

    meetings = (
        db.query(Meeting)
        .order_by(Meeting.meeting_time.asc(), Meeting.id.asc())
        .all()
    )

    return {
        "meeting_count": scheduled_count,
        "total_meeting_count": len(meetings),
        "meetings": [
            {
                "id": meeting.id,
                "lead_id": meeting.lead_id,
                "meeting_title": meeting.meeting_title,
                "meeting_time": (
                    meeting.meeting_time.isoformat()
                    if meeting.meeting_time
                    else None
                ),
                "duration_minutes": meeting.duration_minutes,
                "timezone": meeting.timezone,
                "status": meeting.status,
                "meeting_link": meeting.meeting_link,
            }
            for meeting in meetings
        ],
    }


# One-time correction for a lead whose workflow status was overwritten.
@router.patch("/{lead_id}/restore-workflow-status")
def restore_workflow_status(
    lead_id: int,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    # Only restore discovery candidates currently marked Potential.
    if (
        lead.source != "hacker_news"
        or lead.status != "Potential"
    ):
        raise HTTPException(
            status_code=409,
            detail="Lead does not match the expected correction conditions.",
        )

    lead.status = "New"

    try:
        db.commit()
        db.refresh(lead)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to restore lead workflow status")
        raise HTTPException(
            status_code=500,
            detail="Failed to restore workflow status.",
        ) from exc

    return {
        "lead_id": lead.id,
        "category": lead.category,
        "status": lead.status,
        "message": "Workflow status restored to New.",
    }
