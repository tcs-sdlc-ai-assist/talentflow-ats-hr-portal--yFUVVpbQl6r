from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(str, Enum):
    DRAFT = "Draft"
    OPEN = "Open"
    ON_HOLD = "On Hold"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class JobType(str, Enum):
    FULL_TIME = "Full-Time"
    PART_TIME = "Part-Time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    TEMPORARY = "Temporary"


class ExperienceLevel(str, Enum):
    ENTRY = "Entry"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"
    EXECUTIVE = "Executive"


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of records per page")
    total_pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(from_attributes=True)


class JobBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Job title")
    description: Optional[str] = Field(None, description="Full job description")
    department: Optional[str] = Field(None, max_length=100, description="Department name")
    location: Optional[str] = Field(None, max_length=200, description="Job location")
    job_type: Optional[JobType] = Field(None, description="Type of employment")
    experience_level: Optional[ExperienceLevel] = Field(None, description="Required experience level")
    salary_min: Optional[float] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[float] = Field(None, ge=0, description="Maximum salary")
    salary_currency: Optional[str] = Field("USD", max_length=3, description="Salary currency code")
    requirements: Optional[str] = Field(None, description="Job requirements")
    responsibilities: Optional[str] = Field(None, description="Job responsibilities")
    benefits: Optional[str] = Field(None, description="Job benefits")
    is_remote: bool = Field(False, description="Whether the job is remote")
    openings: int = Field(1, ge=1, description="Number of open positions")

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and info.data.get("salary_min") is not None:
            if v < info.data["salary_min"]:
                raise ValueError("salary_max must be greater than or equal to salary_min")
        return v

    @field_validator("title")
    @classmethod
    def validate_title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be blank")
        return v.strip()


class JobCreate(JobBase):
    status: JobStatus = Field(JobStatus.DRAFT, description="Initial job status")

    model_config = ConfigDict(from_attributes=True)


class JobUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Job title")
    description: Optional[str] = Field(None, description="Full job description")
    department: Optional[str] = Field(None, max_length=100, description="Department name")
    location: Optional[str] = Field(None, max_length=200, description="Job location")
    job_type: Optional[JobType] = Field(None, description="Type of employment")
    experience_level: Optional[ExperienceLevel] = Field(None, description="Required experience level")
    salary_min: Optional[float] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[float] = Field(None, ge=0, description="Maximum salary")
    salary_currency: Optional[str] = Field(None, max_length=3, description="Salary currency code")
    requirements: Optional[str] = Field(None, description="Job requirements")
    responsibilities: Optional[str] = Field(None, description="Job responsibilities")
    benefits: Optional[str] = Field(None, description="Job benefits")
    is_remote: Optional[bool] = Field(None, description="Whether the job is remote")
    openings: Optional[int] = Field(None, ge=1, description="Number of open positions")

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and info.data.get("salary_min") is not None:
            if v < info.data["salary_min"]:
                raise ValueError("salary_max must be greater than or equal to salary_min")
        return v

    @field_validator("title")
    @classmethod
    def validate_title_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Title cannot be blank")
        return v.strip() if v is not None else v

    model_config = ConfigDict(from_attributes=True)


class JobStatusUpdate(BaseModel):
    status: JobStatus = Field(..., description="New job status")

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: str = Field(..., description="Job unique identifier")
    title: str = Field(..., description="Job title")
    description: Optional[str] = Field(None, description="Full job description")
    department: Optional[str] = Field(None, description="Department name")
    location: Optional[str] = Field(None, description="Job location")
    job_type: Optional[str] = Field(None, description="Type of employment")
    experience_level: Optional[str] = Field(None, description="Required experience level")
    salary_min: Optional[float] = Field(None, description="Minimum salary")
    salary_max: Optional[float] = Field(None, description="Maximum salary")
    salary_currency: Optional[str] = Field(None, description="Salary currency code")
    requirements: Optional[str] = Field(None, description="Job requirements")
    responsibilities: Optional[str] = Field(None, description="Job responsibilities")
    benefits: Optional[str] = Field(None, description="Job benefits")
    is_remote: bool = Field(False, description="Whether the job is remote")
    openings: int = Field(1, description="Number of open positions")
    status: str = Field(..., description="Current job status")
    created_by: Optional[str] = Field(None, description="ID of user who created the job")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class JobBriefResponse(BaseModel):
    id: str = Field(..., description="Job unique identifier")
    title: str = Field(..., description="Job title")
    department: Optional[str] = Field(None, description="Department name")
    location: Optional[str] = Field(None, description="Job location")
    job_type: Optional[str] = Field(None, description="Type of employment")
    status: str = Field(..., description="Current job status")
    openings: int = Field(1, description="Number of open positions")
    is_remote: bool = Field(False, description="Whether the job is remote")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    data: list[JobBriefResponse] = Field(..., description="List of jobs")
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    model_config = ConfigDict(from_attributes=True)


class JobFilterParams(BaseModel):
    status: Optional[JobStatus] = Field(None, description="Filter by job status")
    department: Optional[str] = Field(None, description="Filter by department")
    job_type: Optional[JobType] = Field(None, description="Filter by job type")
    experience_level: Optional[ExperienceLevel] = Field(None, description="Filter by experience level")
    is_remote: Optional[bool] = Field(None, description="Filter by remote status")
    search: Optional[str] = Field(None, description="Search in title and description")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Number of records per page")

    model_config = ConfigDict(from_attributes=True)