import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SkillInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100)
    years_of_experience: Optional[int] = Field(default=None, ge=0, le=50)


class CandidateCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    headline: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    linkedin_url: Optional[str] = Field(default=None, max_length=500)
    portfolio_url: Optional[str] = Field(default=None, max_length=500)
    resume_url: Optional[str] = Field(default=None, max_length=500)
    source: Optional[str] = Field(default=None, max_length=100)
    skills: Optional[list[SkillInfo]] = Field(default=None)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                return None
            return cleaned
        return v

    @field_validator("linkedin_url", "portfolio_url", "resume_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                return None
            if not cleaned.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return cleaned
        return v


class CandidateUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    headline: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    linkedin_url: Optional[str] = Field(default=None, max_length=500)
    portfolio_url: Optional[str] = Field(default=None, max_length=500)
    resume_url: Optional[str] = Field(default=None, max_length=500)
    source: Optional[str] = Field(default=None, max_length=100)
    skills: Optional[list[SkillInfo]] = Field(default=None)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                return None
            return cleaned
        return v

    @field_validator("linkedin_url", "portfolio_url", "resume_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                return None
            if not cleaned.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return cleaned
        return v


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    resume_url: Optional[str] = None
    source: Optional[str] = None
    skills: list[SkillInfo] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CandidateResponse]
    total: int
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)