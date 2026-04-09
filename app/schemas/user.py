import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: Optional[str] = Field(default="Viewer")

    @field_validator("username")
    @classmethod
    def username_must_be_alphanumeric(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username must not be empty")
        if not all(c.isalnum() or c in ("_", "-", ".") for c in v):
            raise ValueError(
                "Username must contain only alphanumeric characters, underscores, hyphens, or dots"
            )
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> str:
        allowed_roles = {
            "Super Admin",
            "Admin",
            "Hiring Manager",
            "Recruiter",
            "Interviewer",
            "Viewer",
        }
        if v is None:
            return "Viewer"
        if v not in allowed_roles:
            raise ValueError(
                f"Invalid role '{v}'. Allowed roles: {', '.join(sorted(allowed_roles))}"
            )
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    created_at: datetime


class UserContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse