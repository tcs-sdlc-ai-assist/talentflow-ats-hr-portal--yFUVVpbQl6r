import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class AuditLogCreate(BaseModel):
    action: str = Field(..., min_length=1, max_length=255, description="Action performed")
    entity_type: str = Field(..., min_length=1, max_length=100, description="Type of entity affected")
    entity_id: str = Field(..., min_length=1, max_length=36, description="ID of the entity affected")
    details: Optional[dict] = Field(default=None, description="Additional details about the action")
    actor_id: str = Field(..., min_length=1, max_length=36, description="ID of the user who performed the action")

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    details: Optional[dict] = None
    actor_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogFilterParams(BaseModel):
    action: Optional[str] = Field(default=None, description="Filter by action type")
    entity_type: Optional[str] = Field(default=None, description="Filter by entity type")
    entity_id: Optional[str] = Field(default=None, description="Filter by entity ID")
    actor_id: Optional[str] = Field(default=None, description="Filter by actor ID")
    start_date: Optional[datetime] = Field(default=None, description="Filter logs from this date")
    end_date: Optional[datetime] = Field(default=None, description="Filter logs until this date")

    @field_validator("end_date")
    @classmethod
    def end_date_after_start_date(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is not None and info.data.get("start_date") is not None:
            if v < info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int = Field(..., ge=0, description="Total number of matching records")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    model_config = ConfigDict(from_attributes=True)