import logging
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewFeedback
from app.models.job import Job
from app.models.user import User

logger = logging.getLogger(__name__)


class InterviewService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def schedule_interview(
        self,
        application_id: str,
        interviewer_id: str,
        scheduled_at: datetime,
        interview_type: str,
        duration_minutes: int = 60,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Interview:
        result = await self.db.execute(
            select(Application).where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        if not application:
            raise ValueError(f"Application with id '{application_id}' not found")

        if application.status in ("Hired", "Rejected", "Withdrawn"):
            raise ValueError(
                f"Cannot schedule interview for application with status '{application.status}'"
            )

        result = await self.db.execute(
            select(User).where(User.id == interviewer_id)
        )
        interviewer = result.scalar_one_or_none()
        if not interviewer:
            raise ValueError(f"Interviewer with id '{interviewer_id}' not found")

        interview = Interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_at,
            interview_type=interview_type,
            duration_minutes=duration_minutes,
            location=location,
            notes=notes,
            status="Scheduled",
        )
        self.db.add(interview)
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "Interview scheduled: id=%s, application_id=%s, interviewer_id=%s, type=%s",
            interview.id,
            application_id,
            interviewer_id,
            interview_type,
        )
        return interview

    async def list_interviews(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        interview_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        application_id: Optional[str] = None,
    ) -> dict:
        query = select(Interview).options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
            selectinload(Interview.interviewer),
            selectinload(Interview.feedback),
        )

        count_query = select(func.count(Interview.id))

        conditions = []
        if status:
            conditions.append(Interview.status == status)
        if interview_type:
            conditions.append(Interview.interview_type == interview_type)
        if from_date:
            conditions.append(Interview.scheduled_at >= from_date)
        if to_date:
            conditions.append(Interview.scheduled_at <= to_date)
        if application_id:
            conditions.append(Interview.application_id == application_id)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        total_pages = max(1, math.ceil(total / page_size))
        offset = (page - 1) * page_size

        query = query.order_by(Interview.scheduled_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        interviews = result.scalars().all()

        items = []
        for interview in interviews:
            item = self._interview_to_dict(interview)
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def get_interview(self, interview_id: str) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
                selectinload(Interview.feedback),
            )
        )
        return result.scalar_one_or_none()

    async def update_interview(
        self,
        interview_id: str,
        scheduled_at: Optional[datetime] = None,
        interview_type: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Interview:
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError(f"Interview with id '{interview_id}' not found")

        if scheduled_at is not None:
            interview.scheduled_at = scheduled_at
        if interview_type is not None:
            interview.interview_type = interview_type
        if duration_minutes is not None:
            interview.duration_minutes = duration_minutes
        if location is not None:
            interview.location = location
        if notes is not None:
            interview.notes = notes
        if status is not None:
            interview.status = status

        interview.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info("Interview updated: id=%s", interview_id)
        return interview

    async def cancel_interview(self, interview_id: str) -> Interview:
        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError(f"Interview with id '{interview_id}' not found")

        if interview.status == "Cancelled":
            raise ValueError("Interview is already cancelled")

        interview.status = "Cancelled"
        interview.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info("Interview cancelled: id=%s", interview_id)
        return interview

    async def list_my_interviews(
        self,
        interviewer_id: str,
        page: int = 1,
        page_size: int = 20,
        filter_type: Optional[str] = None,
    ) -> dict:
        query = select(Interview).options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
            selectinload(Interview.interviewer),
            selectinload(Interview.feedback),
        ).where(Interview.interviewer_id == interviewer_id)

        count_query = select(func.count(Interview.id)).where(
            Interview.interviewer_id == interviewer_id
        )

        now = datetime.now(timezone.utc)

        if filter_type == "upcoming":
            query = query.where(
                and_(
                    Interview.status == "Scheduled",
                    Interview.scheduled_at >= now,
                )
            )
            count_query = count_query.where(
                and_(
                    Interview.status == "Scheduled",
                    Interview.scheduled_at >= now,
                )
            )
        elif filter_type == "pending_feedback":
            query = query.where(Interview.status == "Completed")
            count_query = count_query.where(Interview.status == "Completed")

            subquery = select(InterviewFeedback.interview_id)
            query = query.where(Interview.id.notin_(subquery))
            count_query = count_query.where(Interview.id.notin_(subquery))
        elif filter_type == "completed":
            query = query.where(Interview.status == "Completed")
            count_query = count_query.where(Interview.status == "Completed")

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        total_pages = max(1, math.ceil(total / page_size))
        offset = (page - 1) * page_size

        query = query.order_by(Interview.scheduled_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        interviews = result.scalars().all()

        pending_feedback_count_query = (
            select(func.count(Interview.id))
            .where(
                and_(
                    Interview.interviewer_id == interviewer_id,
                    Interview.status == "Completed",
                    Interview.id.notin_(select(InterviewFeedback.interview_id)),
                )
            )
        )
        pf_result = await self.db.execute(pending_feedback_count_query)
        pending_feedback_count = pf_result.scalar() or 0

        items = []
        for interview in interviews:
            item = self._interview_to_dict(interview)
            has_feedback = interview.feedback is not None
            needs_feedback = interview.status == "Completed" and not has_feedback
            item["has_feedback"] = has_feedback
            item["needs_feedback"] = needs_feedback
            if has_feedback and interview.feedback:
                item["feedback_rating"] = interview.feedback.rating
            else:
                item["feedback_rating"] = None
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "pending_feedback_count": pending_feedback_count,
        }

    async def submit_feedback(
        self,
        interview_id: str,
        interviewer_id: str,
        rating: int,
        feedback_text: str,
        recommendation: Optional[str] = None,
        strengths: Optional[str] = None,
        weaknesses: Optional[str] = None,
    ) -> InterviewFeedback:
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        if not feedback_text or not feedback_text.strip():
            raise ValueError("Feedback text is required")

        if recommendation is not None:
            allowed_recommendations = {"strong_hire", "hire", "no_hire", "strong_no_hire"}
            if recommendation not in allowed_recommendations:
                raise ValueError(
                    f"Invalid recommendation '{recommendation}'. "
                    f"Must be one of: {', '.join(sorted(allowed_recommendations))}"
                )

        interview = await self.get_interview(interview_id)
        if not interview:
            raise ValueError(f"Interview with id '{interview_id}' not found")

        if interview.interviewer_id != interviewer_id:
            raise ValueError("Only the assigned interviewer can submit feedback for this interview")

        result = await self.db.execute(
            select(InterviewFeedback).where(
                InterviewFeedback.interview_id == interview_id
            )
        )
        existing_feedback = result.scalar_one_or_none()

        if existing_feedback:
            existing_feedback.rating = rating
            existing_feedback.feedback_text = feedback_text.strip()
            existing_feedback.recommendation = recommendation
            existing_feedback.strengths = strengths.strip() if strengths else None
            existing_feedback.weaknesses = weaknesses.strip() if weaknesses else None
            existing_feedback.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(existing_feedback)

            logger.info(
                "Interview feedback updated: interview_id=%s, interviewer_id=%s",
                interview_id,
                interviewer_id,
            )
            return existing_feedback

        feedback = InterviewFeedback(
            interview_id=interview_id,
            interviewer_id=interviewer_id,
            rating=rating,
            feedback_text=feedback_text.strip(),
            recommendation=recommendation,
            strengths=strengths.strip() if strengths else None,
            weaknesses=weaknesses.strip() if weaknesses else None,
        )
        self.db.add(feedback)

        if interview.status == "Scheduled":
            interview.status = "Completed"
            interview.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(feedback)

        logger.info(
            "Interview feedback submitted: interview_id=%s, interviewer_id=%s, rating=%d",
            interview_id,
            interviewer_id,
            rating,
        )
        return feedback

    async def get_feedback(self, interview_id: str) -> Optional[InterviewFeedback]:
        result = await self.db.execute(
            select(InterviewFeedback)
            .where(InterviewFeedback.interview_id == interview_id)
            .options(
                selectinload(InterviewFeedback.interview),
                selectinload(InterviewFeedback.interviewer),
            )
        )
        return result.scalar_one_or_none()

    async def get_upcoming_interviews(
        self,
        interviewer_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[Interview]:
        now = datetime.now(timezone.utc)
        query = (
            select(Interview)
            .where(
                and_(
                    Interview.status == "Scheduled",
                    Interview.scheduled_at >= now,
                )
            )
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.interviewer),
                selectinload(Interview.feedback),
            )
            .order_by(Interview.scheduled_at.asc())
            .limit(limit)
        )

        if interviewer_id:
            query = query.where(Interview.interviewer_id == interviewer_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_interviews_for_application(
        self, application_id: str
    ) -> list[Interview]:
        result = await self.db.execute(
            select(Interview)
            .where(Interview.application_id == application_id)
            .options(
                selectinload(Interview.interviewer),
                selectinload(Interview.feedback),
            )
            .order_by(Interview.scheduled_at.desc())
        )
        return list(result.scalars().all())

    async def get_interview_stats(
        self,
        interviewer_id: Optional[str] = None,
    ) -> dict:
        base_condition = []
        if interviewer_id:
            base_condition.append(Interview.interviewer_id == interviewer_id)

        total_query = select(func.count(Interview.id))
        if base_condition:
            total_query = total_query.where(and_(*base_condition))
        total_result = await self.db.execute(total_query)
        total = total_result.scalar() or 0

        scheduled_query = select(func.count(Interview.id)).where(
            Interview.status == "Scheduled"
        )
        if base_condition:
            scheduled_query = scheduled_query.where(and_(*base_condition))
        scheduled_result = await self.db.execute(scheduled_query)
        scheduled = scheduled_result.scalar() or 0

        completed_query = select(func.count(Interview.id)).where(
            Interview.status == "Completed"
        )
        if base_condition:
            completed_query = completed_query.where(and_(*base_condition))
        completed_result = await self.db.execute(completed_query)
        completed = completed_result.scalar() or 0

        feedback_subquery = select(InterviewFeedback.interview_id)
        pending_feedback_query = select(func.count(Interview.id)).where(
            and_(
                Interview.status == "Completed",
                Interview.id.notin_(feedback_subquery),
            )
        )
        if base_condition:
            pending_feedback_query = pending_feedback_query.where(and_(*base_condition))
        pf_result = await self.db.execute(pending_feedback_query)
        pending_feedback = pf_result.scalar() or 0

        return {
            "total": total,
            "scheduled": scheduled,
            "completed": completed,
            "pending_feedback": pending_feedback,
        }

    def _interview_to_dict(self, interview: Interview) -> dict:
        candidate_name = None
        candidate_email = None
        job_title = None

        if interview.application:
            if interview.application.candidate:
                candidate = interview.application.candidate
                candidate_name = f"{candidate.first_name} {candidate.last_name}"
                candidate_email = candidate.email
            if interview.application.job:
                job_title = interview.application.job.title

        interviewer_name = None
        if interview.interviewer:
            interviewer_name = interview.interviewer.full_name or interview.interviewer.username

        return {
            "id": interview.id,
            "application_id": interview.application_id,
            "interviewer_id": interview.interviewer_id,
            "scheduled_at": interview.scheduled_at,
            "interview_type": interview.interview_type,
            "duration_minutes": interview.duration_minutes,
            "location": interview.location,
            "notes": interview.notes,
            "status": interview.status,
            "created_at": interview.created_at,
            "updated_at": interview.updated_at,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "job_title": job_title,
            "interviewer_name": interviewer_name,
            "feedback": interview.feedback,
        }