import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column("candidate_id", String(36), ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)
    years_of_experience = Column(Integer, nullable=True)

    candidates = relationship(
        "Candidate",
        secondary=candidate_skills,
        back_populates="skills",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name})>"


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(30), nullable=True)
    headline = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    resume_url = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    skills = relationship(
        "Skill",
        secondary=candidate_skills,
        back_populates="candidates",
        lazy="selectin",
    )

    applications = relationship(
        "Application",
        back_populates="candidate",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, email={self.email})>"