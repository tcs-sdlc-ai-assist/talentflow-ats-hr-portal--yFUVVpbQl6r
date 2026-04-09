import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviewCreate(BaseModel):
    application_id: uuid.UUID
    interviewer_id: uuid.UUID
    scheduled_at: datetime
    interview_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Type of interview, e.g. 'phone_screen', 'technical', 'behavioral', 'onsite'",
    )
    duration_minutes: int = Field(default=60, ge=15, le=480)
    location: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_at_must_be_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            if v < datetime.utcnow():
                raise ValueError("scheduled_at must be in the future")
        return v


class InterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    interview_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    duration_minutes: Optional[int] = Field(default=None, ge=15, le=480)
    location: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(from_attributes=True)


class FeedbackSubmit(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (poor) to 5 (excellent)")
    feedback_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Detailed feedback text about the candidate's performance",
    )
    recommendation: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Recommendation, e.g. 'strong_hire', 'hire', 'no_hire', 'strong_no_hire'",
    )
    strengths: Optional[str] = Field(default=None, max_length=2000)
    weaknesses: Optional[str] = Field(default=None, max_length=2000)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"strong_hire", "hire", "no_hire", "strong_no_hire"}
            if v not in allowed:
                raise ValueError(f"recommendation must be one of {allowed}")
        return v


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    interview_id: uuid.UUID
    interviewer_id: uuid.UUID
    rating: int
    feedback_text: str
    recommendation: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InterviewResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    interviewer_id: uuid.UUID
    scheduled_at: datetime
    interview_type: str
    duration_minutes: int
    location: Optional[str] = None
    notes: Optional[str] = None
    status: str
    feedback: Optional[FeedbackResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InterviewListResponse(BaseModel):
    items: list[InterviewResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)