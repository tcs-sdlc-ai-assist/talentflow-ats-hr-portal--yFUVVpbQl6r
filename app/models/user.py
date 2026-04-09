import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    full_name = Column(String(64), nullable=True, default="")
    role = Column(String(20), nullable=False, default="Interviewer", index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow, onupdate=datetime.utcnow)

    from sqlalchemy.orm import relationship

    jobs = relationship("Job", back_populates="creator", lazy="selectin")
    interviews_as_interviewer = relationship("Interview", back_populates="interviewer", lazy="selectin")
    feedbacks = relationship("InterviewFeedback", back_populates="interviewer", lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="actor", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, username={self.username!r}, role={self.role!r})>"