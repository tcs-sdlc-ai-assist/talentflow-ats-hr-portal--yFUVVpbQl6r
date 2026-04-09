import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    department = Column(String(100), nullable=True)
    location = Column(String(200), nullable=True)
    job_type = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String(3), nullable=True, default="USD")
    requirements = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    is_remote = Column(Boolean, nullable=False, default=False)
    openings = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="Draft")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship("User", back_populates="jobs", lazy="selectin")
    applications = relationship("Application", back_populates="job", lazy="selectin")