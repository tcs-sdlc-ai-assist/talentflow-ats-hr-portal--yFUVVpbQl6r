import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview, InterviewFeedback
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditTrailService
from app.services.dashboard_service import DashboardService, MetricsAggregator

from datetime import datetime, timezone, timedelta
import uuid


async def _create_job(db: AsyncSession, title: str = "Test Job", status: str = "Open", created_by: str = None) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        title=title,
        status=status,
        department="Engineering",
        location="Remote",
        created_by=created_by,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def _create_candidate(db: AsyncSession, email: str = None) -> Candidate:
    if email is None:
        email = f"candidate-{uuid.uuid4().hex[:8]}@example.com"
    candidate = Candidate(
        id=str(uuid.uuid4()),
        first_name="Test",
        last_name="Candidate",
        email=email,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    return candidate


async def _create_application(
    db: AsyncSession,
    job_id: str,
    candidate_id: str,
    status: str = "Applied",
) -> Application:
    application = Application(
        id=str(uuid.uuid4()),
        job_id=job_id,
        candidate_id=candidate_id,
        status=status,
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application


async def _create_interview(
    db: AsyncSession,
    application_id: str,
    interviewer_id: str,
    status: str = "Scheduled",
) -> Interview:
    interview = Interview(
        id=str(uuid.uuid4()),
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        interview_type="technical",
        duration_minutes=60,
        status=status,
    )
    db.add(interview)
    await db.flush()
    await db.refresh(interview)
    return interview


async def _create_audit_log(
    db: AsyncSession,
    actor_id: str,
    action: str = "Test Action",
    entity_type: str = "TestEntity",
    entity_id: str = None,
    details: str = None,
    created_at: datetime = None,
) -> AuditLog:
    if entity_id is None:
        entity_id = str(uuid.uuid4())
    log = AuditLog(
        id=str(uuid.uuid4()),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        actor_id=actor_id,
    )
    if created_at is not None:
        log.created_at = created_at
    db.add(log)
    await db.flush()
    await db.refresh(log)
    return log


# ============================================================
# Dashboard Page Tests
# ============================================================


class TestDashboardPage:
    """Tests for the main dashboard page."""

    async def test_dashboard_requires_authentication(self, unauthenticated_client: AsyncClient):
        response = await unauthenticated_client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (302, 401, 403)

    async def test_admin_dashboard_shows_metrics(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, title="Admin Job", created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        await _create_application(db_session, job.id, candidate.id)
        await db_session.commit()

        response = await admin_client.get("/dashboard")
        assert response.status_code == 200
        text = response.text
        assert "Dashboard" in text
        assert "Total Jobs" in text or "total_jobs" in text.lower()

    async def test_admin_dashboard_shows_pipeline_stats(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        c1 = await _create_candidate(db_session, email="c1@example.com")
        c2 = await _create_candidate(db_session, email="c2@example.com")
        await _create_application(db_session, job.id, c1.id, status="Applied")
        await _create_application(db_session, job.id, c2.id, status="Interview")
        await db_session.commit()

        response = await admin_client.get("/dashboard")
        assert response.status_code == 200
        assert "Pipeline" in response.text or "pipeline" in response.text.lower()

    async def test_admin_dashboard_shows_recent_audit_logs(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(
            db_session,
            actor_id=admin_user.id,
            action="Job Created",
            entity_type="Job",
        )
        await db_session.commit()

        response = await admin_client.get("/dashboard")
        assert response.status_code == 200
        assert "Recent Activity" in response.text or "Activity" in response.text

    async def test_hiring_manager_dashboard(
        self,
        hiring_manager_client: AsyncClient,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        await _create_job(db_session, title="HM Job", status="Open", created_by=hiring_manager_user.id)
        await db_session.commit()

        response = await hiring_manager_client.get("/dashboard")
        assert response.status_code == 200
        text = response.text
        assert "Dashboard" in text

    async def test_recruiter_dashboard(
        self,
        recruiter_client: AsyncClient,
        db_session: AsyncSession,
        recruiter_user: User,
    ):
        await _create_job(db_session, title="Recruiter Job", created_by=recruiter_user.id)
        await db_session.commit()

        response = await recruiter_client.get("/dashboard")
        assert response.status_code == 200
        assert "Dashboard" in response.text

    async def test_interviewer_dashboard_shows_upcoming_interviews(
        self,
        interviewer_client: AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, interviewer_user.id, status="Scheduled")
        await db_session.commit()

        response = await interviewer_client.get("/dashboard")
        assert response.status_code == 200
        text = response.text
        assert "Interview" in text or "interview" in text.lower()

    async def test_interviewer_dashboard_shows_pending_feedback(
        self,
        interviewer_client: AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, interviewer_user.id, status="Completed")
        await db_session.commit()

        response = await interviewer_client.get("/dashboard")
        assert response.status_code == 200
        text = response.text
        assert "Pending" in text or "Feedback" in text or "pending" in text.lower()

    async def test_viewer_dashboard(self, viewer_client: AsyncClient):
        response = await viewer_client.get("/dashboard")
        assert response.status_code == 200
        assert "Welcome" in response.text or "Dashboard" in response.text


# ============================================================
# Dashboard Metrics API Tests
# ============================================================


class TestDashboardMetricsAPI:
    """Tests for the /api/dashboard/metrics endpoint."""

    async def test_metrics_api_requires_auth(self, unauthenticated_client: AsyncClient):
        response = await unauthenticated_client.get("/api/dashboard/metrics", follow_redirects=False)
        assert response.status_code in (302, 401, 403)

    async def test_metrics_api_returns_json(self, admin_client: AsyncClient):
        response = await admin_client.get("/api/dashboard/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "role" in data
        assert "metrics" in data
        assert data["role"] == "Admin"

    async def test_metrics_api_counts_jobs(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_job(db_session, title="Job 1", status="Open", created_by=admin_user.id)
        await _create_job(db_session, title="Job 2", status="Draft", created_by=admin_user.id)
        await _create_job(db_session, title="Job 3", status="Open", created_by=admin_user.id)
        await db_session.commit()

        response = await admin_client.get("/api/dashboard/metrics")
        assert response.status_code == 200
        data = response.json()
        metrics = data["metrics"]
        assert metrics["total_jobs"] == 3
        assert metrics["open_jobs"] == 2

    async def test_metrics_api_counts_candidates(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(db_session, email="m1@example.com")
        await _create_candidate(db_session, email="m2@example.com")
        await db_session.commit()

        response = await admin_client.get("/api/dashboard/metrics")
        data = response.json()
        assert data["metrics"]["total_candidates"] == 2

    async def test_metrics_api_counts_applications(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        c1 = await _create_candidate(db_session, email="a1@example.com")
        c2 = await _create_candidate(db_session, email="a2@example.com")
        await _create_application(db_session, job.id, c1.id)
        await _create_application(db_session, job.id, c2.id)
        await db_session.commit()

        response = await admin_client.get("/api/dashboard/metrics")
        data = response.json()
        assert data["metrics"]["total_applications"] == 2

    async def test_metrics_api_counts_interviews(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, admin_user.id, status="Scheduled")
        await _create_interview(db_session, application.id, admin_user.id, status="Completed")
        await db_session.commit()

        response = await admin_client.get("/api/dashboard/metrics")
        data = response.json()
        assert data["metrics"]["total_interviews"] == 2
        assert data["metrics"]["scheduled_interviews"] == 1
        assert data["metrics"]["completed_interviews"] == 1


# ============================================================
# Audit Logs Page Tests
# ============================================================


class TestAuditLogsPage:
    """Tests for the /dashboard/audit-logs page."""

    async def test_audit_logs_page_requires_admin(self, unauthenticated_client: AsyncClient):
        response = await unauthenticated_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert response.status_code in (302, 401, 403)

    async def test_audit_logs_page_forbidden_for_interviewer(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert response.status_code == 403

    async def test_audit_logs_page_forbidden_for_recruiter(
        self,
        recruiter_client: AsyncClient,
    ):
        response = await recruiter_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert response.status_code == 403

    async def test_audit_logs_page_forbidden_for_hiring_manager(
        self,
        hiring_manager_client: AsyncClient,
    ):
        response = await hiring_manager_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert response.status_code == 403

    async def test_audit_logs_page_forbidden_for_viewer(
        self,
        viewer_client: AsyncClient,
    ):
        response = await viewer_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert response.status_code == 403

    async def test_audit_logs_page_accessible_by_admin(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Test Action")
        await db_session.commit()

        response = await admin_client.get("/dashboard/audit-logs")
        assert response.status_code == 200
        assert "Test Action" in response.text

    async def test_audit_logs_page_pagination(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        for i in range(25):
            await _create_audit_log(
                db_session,
                actor_id=admin_user.id,
                action=f"Action {i}",
                entity_type="TestEntity",
            )
        await db_session.commit()

        response = await admin_client.get("/dashboard/audit-logs?page=1&page_size=10")
        assert response.status_code == 200

        response2 = await admin_client.get("/dashboard/audit-logs?page=2&page_size=10")
        assert response2.status_code == 200

    async def test_audit_logs_page_filter_by_action(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Job Created", entity_type="Job")
        await _create_audit_log(db_session, actor_id=admin_user.id, action="User Login", entity_type="User")
        await db_session.commit()

        response = await admin_client.get("/dashboard/audit-logs?action=Job+Created")
        assert response.status_code == 200
        assert "Job Created" in response.text

    async def test_audit_logs_page_filter_by_entity_type(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Created", entity_type="Job")
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Updated", entity_type="Candidate")
        await db_session.commit()

        response = await admin_client.get("/dashboard/audit-logs?entity_type=Job")
        assert response.status_code == 200

    async def test_audit_logs_page_filter_by_date_range(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        old_date = datetime(2024, 1, 15, 12, 0, 0)
        recent_date = datetime(2025, 6, 15, 12, 0, 0)

        await _create_audit_log(
            db_session,
            actor_id=admin_user.id,
            action="Old Action",
            entity_type="Job",
            created_at=old_date,
        )
        await _create_audit_log(
            db_session,
            actor_id=admin_user.id,
            action="Recent Action",
            entity_type="Job",
            created_at=recent_date,
        )
        await db_session.commit()

        response = await admin_client.get(
            "/dashboard/audit-logs?start_date=2025-01-01&end_date=2025-12-31"
        )
        assert response.status_code == 200
        assert "Recent Action" in response.text

    async def test_audit_logs_page_empty_state(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/dashboard/audit-logs")
        assert response.status_code == 200


# ============================================================
# Audit Logs API Tests
# ============================================================


class TestAuditLogsAPI:
    """Tests for the /api/audit-logs endpoint."""

    async def test_audit_logs_api_requires_admin(self, unauthenticated_client: AsyncClient):
        response = await unauthenticated_client.get("/api/audit-logs", follow_redirects=False)
        assert response.status_code in (302, 401, 403)

    async def test_audit_logs_api_forbidden_for_interviewer(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/api/audit-logs")
        assert response.status_code == 403

    async def test_audit_logs_api_forbidden_for_recruiter(
        self,
        recruiter_client: AsyncClient,
    ):
        response = await recruiter_client.get("/api/audit-logs")
        assert response.status_code == 403

    async def test_audit_logs_api_forbidden_for_viewer(
        self,
        viewer_client: AsyncClient,
    ):
        response = await viewer_client.get("/api/audit-logs")
        assert response.status_code == 403

    async def test_audit_logs_api_returns_json(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="API Test")
        await db_session.commit()

        response = await admin_client.get("/api/audit-logs")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "pagination" in data
        assert len(data["logs"]) >= 1

    async def test_audit_logs_api_pagination(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        for i in range(15):
            await _create_audit_log(
                db_session,
                actor_id=admin_user.id,
                action=f"API Action {i}",
            )
        await db_session.commit()

        response = await admin_client.get("/api/audit-logs?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 5
        assert data["pagination"]["total"] == 15
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 5
        assert data["pagination"]["total_pages"] == 3

    async def test_audit_logs_api_filter_by_action(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Job Created", entity_type="Job")
        await _create_audit_log(db_session, actor_id=admin_user.id, action="User Login", entity_type="User")
        await db_session.commit()

        response = await admin_client.get("/api/audit-logs?action=Job+Created")
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["logs"][0]["action"] == "Job Created"

    async def test_audit_logs_api_filter_by_entity_type(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Created", entity_type="Job")
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Updated", entity_type="Candidate")
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Deleted", entity_type="Job")
        await db_session.commit()

        response = await admin_client.get("/api/audit-logs?entity_type=Job")
        data = response.json()
        assert data["pagination"]["total"] == 2
        for log in data["logs"]:
            assert log["entity_type"] == "Job"

    async def test_audit_logs_api_filter_by_actor_id(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        hiring_manager_user: User,
    ):
        await _create_audit_log(db_session, actor_id=admin_user.id, action="Admin Action")
        await _create_audit_log(db_session, actor_id=hiring_manager_user.id, action="HM Action")
        await db_session.commit()

        response = await admin_client.get(f"/api/audit-logs?actor_id={admin_user.id}")
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["logs"][0]["action"] == "Admin Action"

    async def test_audit_logs_api_filter_by_date_range(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        old_date = datetime(2024, 3, 15, 12, 0, 0)
        recent_date = datetime(2025, 6, 15, 12, 0, 0)

        await _create_audit_log(
            db_session,
            actor_id=admin_user.id,
            action="Old",
            created_at=old_date,
        )
        await _create_audit_log(
            db_session,
            actor_id=admin_user.id,
            action="Recent",
            created_at=recent_date,
        )
        await db_session.commit()

        response = await admin_client.get(
            "/api/audit-logs?start_date=2025-01-01&end_date=2025-12-31"
        )
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["logs"][0]["action"] == "Recent"

    async def test_audit_logs_api_empty_result(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/api/audit-logs")
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        assert data["pagination"]["total"] == 0


# ============================================================
# MetricsAggregator Service Tests
# ============================================================


class TestMetricsAggregator:
    """Tests for the MetricsAggregator service class."""

    async def test_count_jobs_total(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_job(db_session, title="J1", status="Open", created_by=admin_user.id)
        await _create_job(db_session, title="J2", status="Draft", created_by=admin_user.id)
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        total = await aggregator.count_jobs()
        assert total == 2

    async def test_count_jobs_by_status(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_job(db_session, title="J1", status="Open", created_by=admin_user.id)
        await _create_job(db_session, title="J2", status="Open", created_by=admin_user.id)
        await _create_job(db_session, title="J3", status="Draft", created_by=admin_user.id)
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        open_count = await aggregator.count_jobs(status="Open")
        draft_count = await aggregator.count_jobs(status="Draft")
        assert open_count == 2
        assert draft_count == 1

    async def test_count_jobs_by_creator(
        self,
        db_session: AsyncSession,
        admin_user: User,
        hiring_manager_user: User,
    ):
        await _create_job(db_session, title="Admin Job", created_by=admin_user.id)
        await _create_job(db_session, title="HM Job", created_by=hiring_manager_user.id)
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        admin_jobs = await aggregator.count_jobs(created_by=admin_user.id)
        hm_jobs = await aggregator.count_jobs(created_by=hiring_manager_user.id)
        assert admin_jobs == 1
        assert hm_jobs == 1

    async def test_count_candidates(
        self,
        db_session: AsyncSession,
    ):
        await _create_candidate(db_session, email="x1@example.com")
        await _create_candidate(db_session, email="x2@example.com")
        await _create_candidate(db_session, email="x3@example.com")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        count = await aggregator.count_candidates()
        assert count == 3

    async def test_count_applications_total(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        c1 = await _create_candidate(db_session, email="app1@example.com")
        c2 = await _create_candidate(db_session, email="app2@example.com")
        await _create_application(db_session, job.id, c1.id, status="Applied")
        await _create_application(db_session, job.id, c2.id, status="Interview")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        total = await aggregator.count_applications()
        assert total == 2

    async def test_count_applications_by_status(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        c1 = await _create_candidate(db_session, email="s1@example.com")
        c2 = await _create_candidate(db_session, email="s2@example.com")
        c3 = await _create_candidate(db_session, email="s3@example.com")
        await _create_application(db_session, job.id, c1.id, status="Applied")
        await _create_application(db_session, job.id, c2.id, status="Applied")
        await _create_application(db_session, job.id, c3.id, status="Hired")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        applied = await aggregator.count_applications(status="Applied")
        hired = await aggregator.count_applications(status="Hired")
        assert applied == 2
        assert hired == 1

    async def test_count_interviews_total(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, admin_user.id, status="Scheduled")
        await _create_interview(db_session, application.id, admin_user.id, status="Completed")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        total = await aggregator.count_interviews()
        assert total == 2

    async def test_count_interviews_by_status(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, admin_user.id, status="Scheduled")
        await _create_interview(db_session, application.id, admin_user.id, status="Scheduled")
        await _create_interview(db_session, application.id, admin_user.id, status="Completed")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        scheduled = await aggregator.count_interviews(status="Scheduled")
        completed = await aggregator.count_interviews(status="Completed")
        assert scheduled == 2
        assert completed == 1

    async def test_count_interviews_by_interviewer(
        self,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, admin_user.id)
        await _create_interview(db_session, application.id, interviewer_user.id)
        await _create_interview(db_session, application.id, interviewer_user.id)
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        admin_count = await aggregator.count_interviews(interviewer_id=admin_user.id)
        interviewer_count = await aggregator.count_interviews(interviewer_id=interviewer_user.id)
        assert admin_count == 1
        assert interviewer_count == 2

    async def test_get_pipeline_stats(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        c1 = await _create_candidate(db_session, email="p1@example.com")
        c2 = await _create_candidate(db_session, email="p2@example.com")
        c3 = await _create_candidate(db_session, email="p3@example.com")
        c4 = await _create_candidate(db_session, email="p4@example.com")
        await _create_application(db_session, job.id, c1.id, status="Applied")
        await _create_application(db_session, job.id, c2.id, status="Applied")
        await _create_application(db_session, job.id, c3.id, status="Interview")
        await _create_application(db_session, job.id, c4.id, status="Hired")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        stats = await aggregator.get_pipeline_stats()

        stats_dict = {s["status"]: s for s in stats}
        assert stats_dict["Applied"]["count"] == 2
        assert stats_dict["Interview"]["count"] == 1
        assert stats_dict["Hired"]["count"] == 1
        assert stats_dict["Rejected"]["count"] == 0

        assert stats_dict["Applied"]["percentage"] == 50.0
        assert stats_dict["Interview"]["percentage"] == 25.0
        assert stats_dict["Hired"]["percentage"] == 25.0

    async def test_get_pipeline_stats_empty(
        self,
        db_session: AsyncSession,
    ):
        aggregator = MetricsAggregator(db_session)
        stats = await aggregator.get_pipeline_stats()
        for s in stats:
            assert s["count"] == 0
            assert s["percentage"] == 0.0

    async def test_get_recent_audit_logs(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        for i in range(15):
            await _create_audit_log(
                db_session,
                actor_id=admin_user.id,
                action=f"Log {i}",
            )
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        logs = await aggregator.get_recent_audit_logs(limit=5)
        assert len(logs) == 5

    async def test_get_jobs_for_user(
        self,
        db_session: AsyncSession,
        admin_user: User,
        hiring_manager_user: User,
    ):
        await _create_job(db_session, title="Admin Job 1", created_by=admin_user.id)
        await _create_job(db_session, title="Admin Job 2", created_by=admin_user.id)
        await _create_job(db_session, title="HM Job", created_by=hiring_manager_user.id)
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        admin_jobs = await aggregator.get_jobs_for_user(admin_user.id)
        hm_jobs = await aggregator.get_jobs_for_user(hiring_manager_user.id)
        assert len(admin_jobs) == 2
        assert len(hm_jobs) == 1

    async def test_get_upcoming_interviews(
        self,
        db_session: AsyncSession,
        admin_user: User,
        interviewer_user: User,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)
        await _create_interview(db_session, application.id, interviewer_user.id, status="Scheduled")
        await _create_interview(db_session, application.id, admin_user.id, status="Scheduled")
        await _create_interview(db_session, application.id, interviewer_user.id, status="Completed")
        await db_session.commit()

        aggregator = MetricsAggregator(db_session)
        all_upcoming = await aggregator.get_upcoming_interviews(limit=10)
        assert len(all_upcoming) == 2

        interviewer_upcoming = await aggregator.get_upcoming_interviews(
            interviewer_id=interviewer_user.id, limit=10
        )
        assert len(interviewer_upcoming) == 1


# ============================================================
# AuditTrailService Tests
# ============================================================


class TestAuditTrailService:
    """Tests for the AuditTrailService."""

    async def test_log_action_creates_entry(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        log = await service.log_action(
            actor_id=admin_user.id,
            action="Job Created",
            entity_type="Job",
            entity_id="test-job-id",
            details={"title": "Software Engineer"},
        )
        assert log.id is not None
        assert log.action == "Job Created"
        assert log.entity_type == "Job"
        assert log.entity_id == "test-job-id"
        assert log.actor_id == admin_user.id
        assert '"title"' in log.details

    async def test_log_action_with_string_details(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        log = await service.log_action(
            actor_id=admin_user.id,
            action="Note",
            entity_type="Application",
            entity_id="app-123",
            details="Simple string detail",
        )
        assert log.details == "Simple string detail"

    async def test_log_action_with_no_details(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        log = await service.log_action(
            actor_id=admin_user.id,
            action="Viewed",
            entity_type="Candidate",
            entity_id="cand-456",
        )
        assert log.details is None

    async def test_query_logs_returns_results(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        await service.log_action(
            actor_id=admin_user.id,
            action="Action 1",
            entity_type="Job",
            entity_id="j1",
        )
        await service.log_action(
            actor_id=admin_user.id,
            action="Action 2",
            entity_type="Candidate",
            entity_id="c1",
        )
        await db_session.commit()

        logs, total = await service.query_logs()
        assert total == 2
        assert len(logs) == 2

    async def test_query_logs_filter_by_action(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        await service.log_action(actor_id=admin_user.id, action="Created", entity_type="Job", entity_id="j1")
        await service.log_action(actor_id=admin_user.id, action="Deleted", entity_type="Job", entity_id="j2")
        await db_session.commit()

        logs, total = await service.query_logs(action="Created")
        assert total == 1
        assert logs[0].action == "Created"

    async def test_query_logs_filter_by_entity_type(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        await service.log_action(actor_id=admin_user.id, action="A", entity_type="Job", entity_id="j1")
        await service.log_action(actor_id=admin_user.id, action="B", entity_type="Candidate", entity_id="c1")
        await service.log_action(actor_id=admin_user.id, action="C", entity_type="Job", entity_id="j2")
        await db_session.commit()

        logs, total = await service.query_logs(entity_type="Job")
        assert total == 2

    async def test_query_logs_pagination(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        for i in range(12):
            await service.log_action(
                actor_id=admin_user.id,
                action=f"Action {i}",
                entity_type="Test",
                entity_id=f"t{i}",
            )
        await db_session.commit()

        logs_p1, total = await service.query_logs(page=1, page_size=5)
        assert total == 12
        assert len(logs_p1) == 5

        logs_p2, _ = await service.query_logs(page=2, page_size=5)
        assert len(logs_p2) == 5

        logs_p3, _ = await service.query_logs(page=3, page_size=5)
        assert len(logs_p3) == 2

    async def test_get_log_by_id(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        log = await service.log_action(
            actor_id=admin_user.id,
            action="Find Me",
            entity_type="Test",
            entity_id="t1",
        )
        await db_session.commit()

        found = await service.get_log_by_id(log.id)
        assert found is not None
        assert found.action == "Find Me"

    async def test_get_log_by_id_not_found(
        self,
        db_session: AsyncSession,
    ):
        service = AuditTrailService(db_session)
        found = await service.get_log_by_id("nonexistent-id")
        assert found is None

    async def test_get_recent_logs(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = AuditTrailService(db_session)
        for i in range(8):
            await service.log_action(
                actor_id=admin_user.id,
                action=f"Recent {i}",
                entity_type="Test",
                entity_id=f"r{i}",
            )
        await db_session.commit()

        recent = await service.get_recent_logs(limit=3)
        assert len(recent) == 3

    async def test_compute_total_pages(self):
        assert AuditTrailService.compute_total_pages(0, 10) == 0
        assert AuditTrailService.compute_total_pages(1, 10) == 1
        assert AuditTrailService.compute_total_pages(10, 10) == 1
        assert AuditTrailService.compute_total_pages(11, 10) == 2
        assert AuditTrailService.compute_total_pages(100, 20) == 5
        assert AuditTrailService.compute_total_pages(101, 20) == 6
        assert AuditTrailService.compute_total_pages(5, 0) == 0

    async def test_parse_details_dict(self):
        result = AuditTrailService.parse_details('{"key": "value"}')
        assert result == {"key": "value"}

    async def test_parse_details_non_dict_json(self):
        result = AuditTrailService.parse_details('"just a string"')
        assert result == {"value": "just a string"}

    async def test_parse_details_invalid_json(self):
        result = AuditTrailService.parse_details("not json at all")
        assert result == {"raw": "not json at all"}

    async def test_parse_details_none(self):
        result = AuditTrailService.parse_details(None)
        assert result is None


# ============================================================
# DashboardService Tests
# ============================================================


class TestDashboardService:
    """Tests for the DashboardService."""

    async def test_get_metrics_returns_all_fields(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = DashboardService(db_session)
        metrics = await service.get_metrics(admin_user)

        assert "total_jobs" in metrics
        assert "open_jobs" in metrics
        assert "total_candidates" in metrics
        assert "total_applications" in metrics
        assert "total_interviews" in metrics
        assert "scheduled_interviews" in metrics
        assert "completed_interviews" in metrics

    async def test_get_metrics_accuracy(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        await _create_job(db_session, title="J1", status="Open", created_by=admin_user.id)
        await _create_job(db_session, title="J2", status="Closed", created_by=admin_user.id)
        c1 = await _create_candidate(db_session, email="ma1@example.com")
        c2 = await _create_candidate(db_session, email="ma2@example.com")
        await db_session.commit()

        service = DashboardService(db_session)
        metrics = await service.get_metrics(admin_user)
        assert metrics["total_jobs"] == 2
        assert metrics["open_jobs"] == 1
        assert metrics["total_candidates"] == 2

    async def test_get_dashboard_context_admin(
        self,
        db_session: AsyncSession,
        admin_user: User,
    ):
        service = DashboardService(db_session)
        context = await service.get_dashboard_context(admin_user)

        assert "stats" in context
        assert "pipeline_stats" in context
        assert "recent_audit_logs" in context
        assert "upcoming_interviews" in context

    async def test_get_dashboard_context_hiring_manager(
        self,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        service = DashboardService(db_session)
        context = await service.get_dashboard_context(hiring_manager_user)

        assert "my_jobs" in context
        assert "upcoming_interviews" in context
        assert "stats" in context

    async def test_get_dashboard_context_recruiter(
        self,
        db_session: AsyncSession,
        recruiter_user: User,
    ):
        service = DashboardService(db_session)
        context = await service.get_dashboard_context(recruiter_user)

        assert "stats" in context
        assert "pipeline_stats" in context
        assert "upcoming_interviews" in context

    async def test_get_dashboard_context_interviewer(
        self,
        db_session: AsyncSession,
        interviewer_user: User,
    ):
        service = DashboardService(db_session)
        context = await service.get_dashboard_context(interviewer_user)

        assert "upcoming_interviews" in context
        assert "pending_feedback" in context

    async def test_get_dashboard_context_viewer(
        self,
        db_session: AsyncSession,
        viewer_user: User,
    ):
        service = DashboardService(db_session)
        context = await service.get_dashboard_context(viewer_user)
        assert "error" not in context