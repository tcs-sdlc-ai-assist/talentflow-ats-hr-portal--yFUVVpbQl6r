import logging
import math
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    ExperienceLevel,
    JobCreate,
    JobFilterParams,
    JobStatus,
    JobType,
    JobUpdate,
)

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, job_data: JobCreate, user_id: Optional[str] = None) -> Job:
        job = Job(
            title=job_data.title,
            description=job_data.description,
            department=job_data.department,
            location=job_data.location,
            job_type=job_data.job_type.value if job_data.job_type else None,
            experience_level=job_data.experience_level.value if job_data.experience_level else None,
            salary_min=job_data.salary_min,
            salary_max=job_data.salary_max,
            salary_currency=job_data.salary_currency,
            requirements=job_data.requirements,
            responsibilities=job_data.responsibilities,
            benefits=job_data.benefits,
            is_remote=job_data.is_remote,
            openings=job_data.openings,
            status=job_data.status.value if job_data.status else JobStatus.DRAFT.value,
            created_by=user_id,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        logger.info("Created job id=%s title=%s by user=%s", job.id, job.title, user_id)
        return job

    async def update_job(self, job_id: str, job_data: JobUpdate) -> Optional[Job]:
        job = await self.get_job(job_id)
        if job is None:
            return None

        update_fields = job_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if field == "job_type" and value is not None:
                value = value.value if isinstance(value, JobType) else value
            elif field == "experience_level" and value is not None:
                value = value.value if isinstance(value, ExperienceLevel) else value
            setattr(job, field, value)

        await self.db.flush()
        await self.db.refresh(job)
        logger.info("Updated job id=%s", job.id)
        return job

    async def update_status(self, job_id: str, status: str) -> Optional[Job]:
        job = await self.get_job(job_id)
        if job is None:
            return None

        valid_statuses = [s.value for s in JobStatus]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

        allowed_transitions: dict[str, list[str]] = {
            "Draft": ["Open", "Cancelled"],
            "Open": ["On Hold", "Closed", "Cancelled"],
            "On Hold": ["Open", "Closed", "Cancelled"],
            "Closed": ["Open"],
            "Cancelled": [],
        }

        current_status = job.status
        allowed = allowed_transitions.get(current_status, [])
        if status not in allowed:
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{status}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none'}"
            )

        job.status = status
        await self.db.flush()
        await self.db.refresh(job)
        logger.info("Updated job id=%s status from %s to %s", job.id, current_status, status)
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        stmt = select(Job).where(Job.id == job_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        filters: Optional[JobFilterParams] = None,
    ) -> dict:
        if filters is None:
            filters = JobFilterParams()

        stmt = select(Job)
        count_stmt = select(func.count()).select_from(Job)

        conditions = []

        if filters.status is not None:
            conditions.append(Job.status == filters.status.value)

        if filters.department is not None:
            conditions.append(Job.department == filters.department)

        if filters.job_type is not None:
            conditions.append(Job.job_type == filters.job_type.value)

        if filters.experience_level is not None:
            conditions.append(Job.experience_level == filters.experience_level.value)

        if filters.is_remote is not None:
            conditions.append(Job.is_remote == filters.is_remote)

        if filters.search is not None and filters.search.strip():
            search_term = f"%{filters.search.strip()}%"
            conditions.append(
                or_(
                    Job.title.ilike(search_term),
                    Job.description.ilike(search_term),
                )
            )

        if conditions:
            for condition in conditions:
                stmt = stmt.where(condition)
                count_stmt = count_stmt.where(condition)

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        total_pages = max(1, math.ceil(total / filters.page_size))

        stmt = stmt.order_by(Job.created_at.desc())
        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.offset(offset).limit(filters.page_size)

        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())

        return {
            "items": jobs,
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
            "total_pages": total_pages,
        }

    async def list_published_jobs(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        department: Optional[str] = None,
        location: Optional[str] = None,
    ) -> dict:
        stmt = select(Job).where(Job.status == JobStatus.OPEN.value)
        count_stmt = select(func.count()).select_from(Job).where(Job.status == JobStatus.OPEN.value)

        if search and search.strip():
            search_term = f"%{search.strip()}%"
            search_condition = or_(
                Job.title.ilike(search_term),
                Job.description.ilike(search_term),
            )
            stmt = stmt.where(search_condition)
            count_stmt = count_stmt.where(search_condition)

        if department and department.strip():
            stmt = stmt.where(Job.department == department.strip())
            count_stmt = count_stmt.where(Job.department == department.strip())

        if location and location.strip():
            location_term = f"%{location.strip()}%"
            stmt = stmt.where(Job.location.ilike(location_term))
            count_stmt = count_stmt.where(Job.location.ilike(location_term))

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        total_pages = max(1, math.ceil(total / page_size))

        stmt = stmt.order_by(Job.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())

        return {
            "items": jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def list_jobs_by_creator(self, user_id: str) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.created_by == user_id)
            .order_by(Job.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_departments(self) -> list[str]:
        stmt = (
            select(Job.department)
            .where(Job.department.isnot(None))
            .where(Job.department != "")
            .distinct()
            .order_by(Job.department)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def validate_hiring_manager(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        allowed_roles = {"Admin", "Super Admin", "Hiring Manager", "Recruiter"}
        if user.role not in allowed_roles:
            return None
        return user

    async def assign_hiring_manager(self, job_id: str, hiring_manager_id: str) -> Optional[Job]:
        job = await self.get_job(job_id)
        if job is None:
            return None

        manager = await self.validate_hiring_manager(hiring_manager_id)
        if manager is None:
            raise ValueError(
                f"User '{hiring_manager_id}' is not a valid hiring manager. "
                "Must be an Admin, Super Admin, Hiring Manager, or Recruiter."
            )

        job.created_by = hiring_manager_id
        await self.db.flush()
        await self.db.refresh(job)
        logger.info("Assigned hiring manager %s to job %s", hiring_manager_id, job_id)
        return job

    async def delete_job(self, job_id: str) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False

        await self.db.delete(job)
        await self.db.flush()
        logger.info("Deleted job id=%s", job_id)
        return True

    async def get_job_count_by_status(self) -> dict[str, int]:
        stmt = (
            select(Job.status, func.count(Job.id))
            .group_by(Job.status)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_total_job_count(self) -> int:
        stmt = select(func.count()).select_from(Job)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def list_hiring_managers(self) -> list[User]:
        allowed_roles = ["Admin", "Super Admin", "Hiring Manager", "Recruiter"]
        stmt = (
            select(User)
            .where(User.role.in_(allowed_roles))
            .order_by(User.username)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())