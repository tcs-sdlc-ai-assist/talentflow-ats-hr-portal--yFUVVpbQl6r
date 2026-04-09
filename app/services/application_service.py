import logging
import math
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.application import (
    ALLOWED_TRANSITIONS,
    VALID_STATUSES,
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatusUpdate,
)

logger = logging.getLogger(__name__)


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_application(
        self,
        data: ApplicationCreate,
        actor_id: Optional[str] = None,
    ) -> Application:
        job_result = await self.db.execute(
            select(Job).where(Job.id == data.job_id)
        )
        job = job_result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job with id '{data.job_id}' not found")

        candidate_result = await self.db.execute(
            select(Candidate).where(Candidate.id == data.candidate_id)
        )
        candidate = candidate_result.scalar_one_or_none()
        if candidate is None:
            raise ValueError(f"Candidate with id '{data.candidate_id}' not found")

        existing_result = await self.db.execute(
            select(Application).where(
                Application.job_id == data.job_id,
                Application.candidate_id == data.candidate_id,
                Application.status.notin_(["Rejected", "Withdrawn"]),
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            raise ValueError(
                f"Candidate '{data.candidate_id}' already has an active application for job '{data.job_id}'"
            )

        application = Application(
            job_id=data.job_id,
            candidate_id=data.candidate_id,
            cover_letter=data.cover_letter,
            resume_url=data.resume_url,
            source=data.source or "Direct",
            status="Applied",
        )
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "Application created: id=%s, job_id=%s, candidate_id=%s, actor=%s",
            application.id,
            application.job_id,
            application.candidate_id,
            actor_id,
        )
        return application

    async def update_status(
        self,
        application_id: str,
        status_update: ApplicationStatusUpdate,
        actor_id: Optional[str] = None,
    ) -> Application:
        result = await self.db.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
                selectinload(Application.interviews),
            )
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise ValueError(f"Application with id '{application_id}' not found")

        current_status = application.status
        new_status = status_update.status

        if new_status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_STATUSES)}"
            )

        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none'}"
            )

        application.status = new_status
        if status_update.notes:
            existing_notes = application.notes or ""
            if existing_notes:
                application.notes = f"{existing_notes}\n\n[Status → {new_status}] {status_update.notes}"
            else:
                application.notes = f"[Status → {new_status}] {status_update.notes}"

        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "Application status updated: id=%s, %s → %s, actor=%s",
            application_id,
            current_status,
            new_status,
            actor_id,
        )
        return application

    async def get_application(self, application_id: str) -> Optional[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
                selectinload(Application.interviews),
            )
        )
        return result.scalar_one_or_none()

    async def list_applications(
        self,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ApplicationListResponse:
        query = select(Application).options(
            selectinload(Application.candidate),
            selectinload(Application.job),
            selectinload(Application.interviews),
        )

        count_query = select(func.count(Application.id))

        if status:
            query = query.where(Application.status == status)
            count_query = count_query.where(Application.status == status)

        if job_id:
            query = query.where(Application.job_id == job_id)
            count_query = count_query.where(Application.job_id == job_id)

        if candidate_id:
            query = query.where(Application.candidate_id == candidate_id)
            count_query = count_query.where(Application.candidate_id == candidate_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        total_pages = max(1, math.ceil(total / page_size))
        offset = (page - 1) * page_size

        query = query.order_by(Application.applied_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        applications = result.scalars().all()

        items = []
        for app in applications:
            candidate_name = None
            if app.candidate:
                candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"

            job_title = None
            if app.job:
                job_title = app.job.title

            items.append(
                ApplicationResponse(
                    id=app.id,
                    job_id=app.job_id,
                    candidate_id=app.candidate_id,
                    status=app.status,
                    cover_letter=app.cover_letter,
                    resume_url=app.resume_url,
                    source=app.source,
                    notes=app.notes,
                    applied_at=app.applied_at,
                    updated_at=app.updated_at,
                    job_title=job_title,
                    candidate_name=candidate_name,
                )
            )

        return ApplicationListResponse(
            items=items,
            total=total,
            page=page,
            size=page_size,
            pages=total_pages,
        )

    async def kanban_view(
        self,
        job_id: Optional[str] = None,
    ) -> dict[str, list[ApplicationResponse]]:
        query = select(Application).options(
            selectinload(Application.candidate),
            selectinload(Application.job),
            selectinload(Application.interviews),
        )

        if job_id:
            query = query.where(Application.job_id == job_id)

        query = query.order_by(Application.applied_at.desc())

        result = await self.db.execute(query)
        applications = result.scalars().all()

        pipeline: dict[str, list[ApplicationResponse]] = {}
        for status in VALID_STATUSES:
            pipeline[status] = []

        for app in applications:
            candidate_name = None
            if app.candidate:
                candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"

            job_title = None
            if app.job:
                job_title = app.job.title

            app_response = ApplicationResponse(
                id=app.id,
                job_id=app.job_id,
                candidate_id=app.candidate_id,
                status=app.status,
                cover_letter=app.cover_letter,
                resume_url=app.resume_url,
                source=app.source,
                notes=app.notes,
                applied_at=app.applied_at,
                updated_at=app.updated_at,
                job_title=job_title,
                candidate_name=candidate_name,
            )

            status_key = app.status
            if status_key in pipeline:
                pipeline[status_key].append(app_response)
            else:
                pipeline[status_key] = [app_response]

        return pipeline

    async def get_applications_for_candidate(
        self,
        candidate_id: str,
    ) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
                selectinload(Application.interviews),
            )
            .order_by(Application.applied_at.desc())
        )
        return list(result.scalars().all())

    async def get_applications_for_job(
        self,
        job_id: str,
    ) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.job_id == job_id)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job),
                selectinload(Application.interviews),
            )
            .order_by(Application.applied_at.desc())
        )
        return list(result.scalars().all())

    async def get_pipeline_stats(self) -> list[dict]:
        stats = []
        total_result = await self.db.execute(
            select(func.count(Application.id))
        )
        total_count = total_result.scalar() or 0

        for status in VALID_STATUSES:
            count_result = await self.db.execute(
                select(func.count(Application.id)).where(
                    Application.status == status
                )
            )
            count = count_result.scalar() or 0
            percentage = (count / total_count * 100) if total_count > 0 else 0

            stats.append(
                {
                    "status": status,
                    "count": count,
                    "percentage": round(percentage, 1),
                }
            )

        return stats