from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    designation = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)
    company_website = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    instagram_url = Column(String(500), nullable=True)
    telegram_id = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    business_requirement = Column(Text, nullable=True)
    company_size = Column(Integer, nullable=True)
    source = Column(String(100), nullable=True)
    icp_score = Column(Integer, default=0)
    category = Column(String(50), default="Not Qualified")
    status = Column(String(100), default="New")
    pain_points = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    buying_intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, nullable=False, index=True)
    role = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Outreach(Base):
    __tablename__ = "outreach"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="Draft")
    response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    meeting_title = Column(String(255), nullable=False, default="Lead Discovery Meeting")
    meeting_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=30)
    timezone = Column(String(100), nullable=False, default="Asia/Kolkata")
    status = Column(String(50), nullable=False, default="Scheduled")
    meeting_link = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)