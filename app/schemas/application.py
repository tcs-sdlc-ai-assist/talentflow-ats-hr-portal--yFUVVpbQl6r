from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Applied": ["Screening", "Rejected", "Withdrawn"],
    "Screening": ["Interview", "Rejected", "Withdrawn"],
    "Interview": ["Assessment", "Offer", "Rejected", "Withdrawn"],
    "Assessment": ["Interview", "Offer", "Rejected", "Withdrawn"],
    "Offer": ["Hired", "Rejected", "Withdrawn"],
    "Hired": [],
    "Rejected": [],
    "Withdrawn": [],
}

VALID_STATUSES = list(ALLOWED_TRANSITIONS.keys())


class ApplicationCreate(BaseModel):
    job_id: str
    candidate_id: str
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    source: Optional[str] = "Direct"

    model_config = ConfigDict(str_strip_whitespace=True)


class ApplicationStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(VALID_STATUSES)}"
            )
        return v


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    status: str
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    applied_at: datetime
    updated_at: datetime
    job_title: Optional[str] = None
    candidate_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int
    page: int
    size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)