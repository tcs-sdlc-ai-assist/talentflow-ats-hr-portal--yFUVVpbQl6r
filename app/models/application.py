import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="Applied", index=True)
    cover_letter = Column(Text, nullable=True)
    resume_url = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True, default="Direct")
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    candidate = relationship("Candidate", back_populates="applications", lazy="selectin")
    job = relationship("Job", back_populates="applications", lazy="selectin")
    interviews = relationship(
        "Interview",
        back_populates="application",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, job_id={self.job_id}, candidate_id={self.candidate_id}, status={self.status})>"