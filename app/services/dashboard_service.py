import logging
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewFeedback
from app.models.job import Job
from app.models.user import User

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Helper class for computing dashboard KPIs from database queries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_jobs(self, status: Optional[str] = None, created_by: Optional[str] = None) -> int:
        stmt = select(func.count(Job.id))
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if created_by is not None:
            stmt = stmt.where(Job.created_by == created_by)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def count_candidates(self) -> int:
        result = await self.db.execute(select(func.count(Candidate.id)))
        return result.scalar() or 0

    async def count_applications(self, status: Optional[str] = None, job_id: Optional[str] = None) -> int:
        stmt = select(func.count(Application.id))
        if status is not None:
            stmt = stmt.where(Application.status == status)
        if job_id is not None:
            stmt = stmt.where(Application.job_id == job_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def count_interviews(
        self,
        status: Optional[str] = None,
        interviewer_id: Optional[str] = None,
    ) -> int:
        stmt = select(func.count(Interview.id))
        if status is not None:
            stmt = stmt.where(Interview.status == status)
        if interviewer_id is not None:
            stmt = stmt.where(Interview.interviewer_id == interviewer_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_pipeline_stats(self) -> list[dict[str, Any]]:
        statuses = [
            "Applied",
            "Screening",
            "Interview",
            "Assessment",
            "Offer",
            "Hired",
            "Rejected",
            "Withdrawn",
        ]
        total_result = await self.db.execute(select(func.count(Application.id)))
        total_apps = total_result.scalar() or 0

        pipeline: list[dict[str, Any]] = []
        for status in statuses:
            count_result = await self.db.execute(
                select(func.count(Application.id)).where(Application.status == status)
            )
            count = count_result.scalar() or 0
            percentage = round((count / total_apps * 100), 1) if total_apps > 0 else 0.0
            pipeline.append(
                {
                    "status": status,
                    "count": count,
                    "percentage": percentage,
                }
            )
        return pipeline

    async def get_recent_audit_logs(self, limit: int = 10) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_jobs_for_user(self, user_id: str) -> list[Job]:
        result = await self.db.execute(
            select(Job).where(Job.created_by == user_id).order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_upcoming_interviews(
        self,
        interviewer_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.status == "Scheduled")
            .order_by(Interview.scheduled_at.asc())
            .limit(limit)
        )
        if interviewer_id is not None:
            stmt = stmt.where(Interview.interviewer_id == interviewer_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_feedback_interviews(self, interviewer_id: str) -> list[Interview]:
        feedback_interview_ids_stmt = select(InterviewFeedback.interview_id)
        stmt = (
            select(Interview)
            .where(
                Interview.interviewer_id == interviewer_id,
                Interview.status == "Completed",
                Interview.id.notin_(feedback_interview_ids_stmt),
            )
            .order_by(Interview.scheduled_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class DashboardService:
    """Service for aggregating dashboard data based on user role."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.aggregator = MetricsAggregator(db)

    async def get_metrics(self, user: User) -> dict[str, Any]:
        try:
            total_jobs = await self.aggregator.count_jobs()
            open_jobs = await self.aggregator.count_jobs(status="Open")
            total_candidates = await self.aggregator.count_candidates()
            total_applications = await self.aggregator.count_applications()
            total_interviews = await self.aggregator.count_interviews()
            scheduled_interviews = await self.aggregator.count_interviews(status="Scheduled")
            completed_interviews = await self.aggregator.count_interviews(status="Completed")

            return {
                "total_jobs": total_jobs,
                "open_jobs": open_jobs,
                "total_candidates": total_candidates,
                "total_applications": total_applications,
                "total_interviews": total_interviews,
                "scheduled_interviews": scheduled_interviews,
                "completed_interviews": completed_interviews,
            }
        except Exception as e:
            logger.error("Error aggregating metrics: %s", e)
            return {
                "total_jobs": 0,
                "open_jobs": 0,
                "total_candidates": 0,
                "total_applications": 0,
                "total_interviews": 0,
                "scheduled_interviews": 0,
                "completed_interviews": 0,
            }

    async def get_dashboard_context(self, user: User) -> dict[str, Any]:
        context: dict[str, Any] = {
            "user": user,
        }

        try:
            role = user.role

            if role in ("Admin", "Super Admin"):
                context.update(await self._get_admin_context(user))
            elif role == "Hiring Manager":
                context.update(await self._get_hiring_manager_context(user))
            elif role == "Recruiter":
                context.update(await self._get_recruiter_context(user))
            elif role == "Interviewer":
                context.update(await self._get_interviewer_context(user))
            else:
                context.update(await self._get_viewer_context(user))

        except Exception as e:
            logger.error("Error building dashboard context for user %s: %s", user.id, e)
            context["error"] = "Unable to load dashboard data. Please try again."

        return context

    async def _get_admin_context(self, user: User) -> dict[str, Any]:
        stats = await self.get_metrics(user)
        pipeline_stats = await self.aggregator.get_pipeline_stats()
        recent_audit_logs = await self.aggregator.get_recent_audit_logs(limit=10)
        upcoming_interviews = await self.aggregator.get_upcoming_interviews(limit=10)

        return {
            "stats": stats,
            "pipeline_stats": pipeline_stats,
            "recent_audit_logs": recent_audit_logs,
            "upcoming_interviews": upcoming_interviews,
        }

    async def _get_recruiter_context(self, user: User) -> dict[str, Any]:
        stats = await self.get_metrics(user)
        pipeline_stats = await self.aggregator.get_pipeline_stats()
        upcoming_interviews = await self.aggregator.get_upcoming_interviews(limit=10)

        return {
            "stats": stats,
            "pipeline_stats": pipeline_stats,
            "upcoming_interviews": upcoming_interviews,
        }

    async def _get_hiring_manager_context(self, user: User) -> dict[str, Any]:
        my_jobs = await self.aggregator.get_jobs_for_user(user.id)
        upcoming_interviews = await self.aggregator.get_upcoming_interviews(limit=10)

        my_job_ids = [job.id for job in my_jobs]
        total_applications = 0
        for job_id in my_job_ids:
            count = await self.aggregator.count_applications(job_id=job_id)
            total_applications += count

        stats = {
            "total_applications": total_applications,
        }

        return {
            "stats": stats,
            "my_jobs": my_jobs,
            "upcoming_interviews": upcoming_interviews,
        }

    async def _get_interviewer_context(self, user: User) -> dict[str, Any]:
        upcoming_interviews = await self.aggregator.get_upcoming_interviews(
            interviewer_id=user.id,
            limit=10,
        )
        pending_feedback = await self.aggregator.get_pending_feedback_interviews(
            interviewer_id=user.id,
        )

        return {
            "upcoming_interviews": upcoming_interviews,
            "pending_feedback": pending_feedback,
        }

    async def _get_viewer_context(self, user: User) -> dict[str, Any]:
        return {}