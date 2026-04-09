import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewFeedback
from app.models.job import Job
from app.models.user import User


async def _create_job(db: AsyncSession, created_by: str) -> Job:
    job = Job(
        title="Software Engineer",
        description="Build things",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        experience_level="Mid",
        status="Open",
        created_by=created_by,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def _create_candidate(db: AsyncSession, email: str = "candidate@example.com") -> Candidate:
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
        email=email,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    return candidate


async def _create_application(db: AsyncSession, job_id: str, candidate_id: str) -> Application:
    application = Application(
        job_id=job_id,
        candidate_id=candidate_id,
        status="Interview",
        source="Direct",
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application


async def _create_interview(
    db: AsyncSession,
    application_id: str,
    interviewer_id: str,
    scheduled_at: datetime | None = None,
    status: str = "Scheduled",
) -> Interview:
    if scheduled_at is None:
        scheduled_at = datetime.now(timezone.utc) + timedelta(days=3)
    interview = Interview(
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_at=scheduled_at,
        interview_type="technical",
        duration_minutes=60,
        location="Zoom",
        status=status,
    )
    db.add(interview)
    await db.flush()
    await db.refresh(interview)
    return interview


# ---------------------------------------------------------------------------
# Schedule Interview Tests
# ---------------------------------------------------------------------------


class TestScheduleInterview:
    """Tests for scheduling interviews."""

    async def test_schedule_interview_form_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Admin can access the schedule interview form."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get(
            f"/interviews/schedule?application_id={application.id}"
        )
        assert response.status_code == 200
        assert "Schedule" in response.text or "schedule" in response.text

    async def test_schedule_interview_submit_creates_interview(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Submitting the schedule form creates an interview record."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        future_dt = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": future_dt,
                "interview_type": "technical",
                "duration_minutes": "60",
                "location": "Conference Room A",
                "notes": "Focus on system design",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Interview).where(Interview.application_id == application.id)
        )
        interview = result.scalar_one_or_none()
        assert interview is not None
        assert interview.interviewer_id == interviewer_user.id
        assert interview.interview_type == "technical"
        assert interview.duration_minutes == 60
        assert interview.status == "Scheduled"

    async def test_schedule_interview_with_invalid_application_id(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Scheduling with a non-existent application ID returns an error."""
        future_dt = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": "nonexistent-id",
                "interviewer_id": interviewer_user.id,
                "scheduled_at": future_dt,
                "interview_type": "phone_screen",
                "duration_minutes": "30",
                "location": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_with_invalid_datetime_format(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Scheduling with an invalid datetime format returns an error."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": "not-a-date",
                "interview_type": "technical",
                "duration_minutes": "60",
                "location": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_recruiter_can_schedule(
        self,
        recruiter_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Recruiter role can schedule interviews."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        future_dt = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await recruiter_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": future_dt,
                "interview_type": "behavioral",
                "duration_minutes": "45",
                "location": "Room B",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_schedule_interview_hiring_manager_can_schedule(
        self,
        hiring_manager_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Hiring Manager role can schedule interviews."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        future_dt = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await hiring_manager_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": future_dt,
                "interview_type": "panel",
                "duration_minutes": "90",
                "location": "Main Office",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303


# ---------------------------------------------------------------------------
# RBAC Tests for Interview Operations
# ---------------------------------------------------------------------------


class TestInterviewRBAC:
    """Tests for role-based access control on interview operations."""

    async def test_interviewer_cannot_schedule_interview(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Interviewer role cannot schedule interviews (403)."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        future_dt = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await interviewer_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": future_dt,
                "interview_type": "technical",
                "duration_minutes": "60",
                "location": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_viewer_cannot_schedule_interview(
        self,
        viewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Viewer role cannot schedule interviews (403)."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        future_dt = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await viewer_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_at": future_dt,
                "interview_type": "technical",
                "duration_minutes": "60",
                "location": "",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_unauthenticated_user_cannot_access_interviews(
        self,
        unauthenticated_client: httpx.AsyncClient,
    ):
        """Unauthenticated users are redirected or get 401 for interview list."""
        response = await unauthenticated_client.get(
            "/interviews",
            follow_redirects=False,
        )
        # require_auth raises 401
        assert response.status_code == 401

    async def test_interviewer_cannot_edit_interview(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Interviewer role cannot edit interviews (403)."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        interview = await _create_interview(
            db_session, application.id, interviewer_user.id
        )

        response = await interviewer_client.post(
            f"/interviews/{interview.id}/edit",
            data={
                "scheduled_at": "",
                "interview_type": "behavioral",
                "duration_minutes": "45",
                "location": "",
                "notes": "",
                "status": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_cancel_interview(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Interviewer role cannot cancel interviews (403)."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        interview = await _create_interview(
            db_session, application.id, interviewer_user.id
        )

        response = await interviewer_client.post(
            f"/interviews/{interview.id}/cancel",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_admin_can_cancel_interview(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Admin can cancel an interview."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        interview = await _create_interview(
            db_session, application.id, interviewer_user.id
        )

        response = await admin_client.post(
            f"/interviews/{interview.id}/cancel",
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(interview)
        assert interview.status == "Cancelled"

    async def test_admin_can_edit_interview(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Admin can edit an interview."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        interview = await _create_interview(
            db_session, application.id, interviewer_user.id
        )

        new_dt = (datetime.now(timezone.utc) + timedelta(days=10)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await admin_client.post(
            f"/interviews/{interview.id}/edit",
            data={
                "scheduled_at": new_dt,
                "interview_type": "behavioral",
                "duration_minutes": "90",
                "location": "Updated Room",
                "notes": "Updated notes",
                "status": "Scheduled",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(interview)
        assert interview.interview_type == "behavioral"
        assert interview.duration_minutes == 90
        assert interview.location == "Updated Room"


# ---------------------------------------------------------------------------
# My Interviews / Assigned Interviews Tests
# ---------------------------------------------------------------------------


class TestMyInterviews:
    """Tests that interviewers see only their assigned interviews."""

    async def test_interviewer_sees_own_interviews(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Interviewer sees interviews assigned to them on /interviews/my."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, interviewer_user.id)

        response = await interviewer_client.get("/interviews/my")
        assert response.status_code == 200
        assert "Jane" in response.text or "technical" in response.text

    async def test_interviewer_does_not_see_others_interviews(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Interviewer does not see interviews assigned to other users."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        # Interview assigned to admin, not the interviewer
        await _create_interview(db_session, application.id, admin_user.id)

        response = await interviewer_client.get("/interviews/my")
        assert response.status_code == 200
        # The page should show 0 total or no interview cards for this user
        assert "No interviews found" in response.text or "0 Total Interviews" in response.text or "0 total" in response.text.lower()

    async def test_my_interviews_filter_upcoming(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Filtering by 'upcoming' shows only future scheduled interviews."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        # Future interview
        await _create_interview(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=7),
            status="Scheduled",
        )

        response = await interviewer_client.get("/interviews/my?filter=upcoming")
        assert response.status_code == 200

    async def test_my_interviews_filter_pending_feedback(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Filtering by 'pending_feedback' shows completed interviews without feedback."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        # Completed interview without feedback
        await _create_interview(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="Completed",
        )

        response = await interviewer_client.get(
            "/interviews/my?filter=pending_feedback"
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Interview Detail Tests
# ---------------------------------------------------------------------------


class TestInterviewDetail:
    """Tests for viewing interview details."""

    async def test_view_interview_detail(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Authenticated user can view interview detail page."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        interview = await _create_interview(
            db_session, application.id, interviewer_user.id
        )

        response = await admin_client.get(f"/interviews/{interview.id}")
        assert response.status_code == 200
        assert "technical" in response.text.lower() or "Technical" in response.text

    async def test_view_nonexistent_interview_returns_404(
        self,
        admin_client: httpx.AsyncClient,
    ):
        """Viewing a non-existent interview returns 404."""
        response = await admin_client.get("/interviews/nonexistent-id-12345")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Feedback Submission Tests
# ---------------------------------------------------------------------------


class TestFeedbackSubmission:
    """Tests for interview feedback submission with rating validation."""

    async def test_submit_feedback_happy_path(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        """Interviewer can submit valid feedback for their assigned interview."""
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        interview = await _create_interview(
            db_session,
            application.id,
            interviewer_user.id,
            status="Scheduled",
        )

        response = await interviewer_client.post(
            f"/interviews/{interview.id}/feedback",
            data={
                "rating": "4",
                "feedback_text": "Strong technical skills demonstrated in system design.",
                "recommendation": "hire",
                "strengths": "Great problem solving",
                "weaknesses": "Could improve communication",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(