import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    interviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_at = Column(DateTime, nullable=False)
    interview_type = Column(String(50), nullable=False, default="phone_screen")
    duration_minutes = Column(Integer, nullable=False, default=60)
    location = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="Scheduled")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("Application", back_populates="interviews", lazy="selectin")
    interviewer = relationship("User", back_populates="interviews", lazy="selectin")
    feedback = relationship("InterviewFeedback", back_populates="interview", uselist=False, lazy="selectin", cascade="all, delete-orphan")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    interview_id = Column(String(36), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    interviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    rating = Column(Integer, nullable=False)
    feedback_text = Column(Text, nullable=False)
    recommendation = Column(String(50), nullable=True)
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    interview = relationship("Interview", back_populates="feedback", lazy="selectin")
    interviewer = relationship("User", back_populates="interview_feedbacks", lazy="selectin")