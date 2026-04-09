import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.schemas.application import ALLOWED_TRANSITIONS, VALID_STATUSES


async def _create_job(db: AsyncSession, created_by: str, status: str = "Open") -> Job:
    """Helper to create a job in the test database."""
    job = Job(
        title="Test Software Engineer",
        description="A test job posting",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        experience_level="Mid",
        status=status,
        created_by=created_by,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def _create_candidate(db: AsyncSession, email: str = "candidate@example.com") -> Candidate:
    """Helper to create a candidate in the test database."""
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
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
    """Helper to create an application in the test database."""
    application = Application(
        job_id=job_id,
        candidate_id=candidate_id,
        status=status,
        source="Direct",
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application


class TestCreateApplication:
    """Tests for creating applications."""

    async def test_create_application_success(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)

        response = await admin_client.post(
            "/applications/new",
            data={
                "job_id": job.id,
                "candidate_id": candidate.id,
                "cover_letter": "I am very interested in this role.",
                "resume_url": "",
                "source": "LinkedIn",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/applications/" in response.headers["location"]

    async def test_create_application_missing_job(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session)

        response = await admin_client.post(
            "/applications/new",
            data={
                "job_id": "nonexistent-job-id",
                "candidate_id": candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "source": "Direct",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_create_application_missing_candidate(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)

        response = await admin_client.post(
            "/applications/new",
            data={
                "job_id": job.id,
                "candidate_id": "nonexistent-candidate-id",
                "cover_letter": "",
                "resume_url": "",
                "source": "Direct",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_create_duplicate_active_application_rejected(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            "/applications/new",
            data={
                "job_id": job.id,
                "candidate_id": candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "source": "Direct",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_create_application_form_page_loads(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await admin_client.get("/applications/new")
        assert response.status_code == 200
        assert "New Application" in response.text or "application" in response.text.lower()


class TestApplicationStatusTransitions:
    """Tests for application status transitions against ALLOWED_TRANSITIONS."""

    async def test_valid_transition_applied_to_screening(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Screening", "notes": "Moving to screening"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_valid_transition_screening_to_interview(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Screening")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Interview", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_valid_transition_interview_to_offer(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Interview")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Offer", "notes": "Extending offer"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_valid_transition_offer_to_hired(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Offer")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Hired", "notes": "Offer accepted"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_valid_transition_applied_to_rejected(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Rejected", "notes": "Not a fit"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_valid_transition_applied_to_withdrawn(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Withdrawn", "notes": "Candidate withdrew"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_all_allowed_transitions_are_valid(self):
        """Verify the ALLOWED_TRANSITIONS dict covers all VALID_STATUSES."""
        for status in VALID_STATUSES:
            assert status in ALLOWED_TRANSITIONS, (
                f"Status '{status}' is in VALID_STATUSES but not in ALLOWED_TRANSITIONS"
            )

    async def test_terminal_states_have_no_transitions(self):
        """Hired, Rejected, and Withdrawn should have no outgoing transitions."""
        assert ALLOWED_TRANSITIONS["Hired"] == []
        assert ALLOWED_TRANSITIONS["Rejected"] == []
        assert ALLOWED_TRANSITIONS["Withdrawn"] == []


class TestInvalidStatusTransitions:
    """Tests for invalid application status transitions."""

    async def test_invalid_transition_applied_to_hired(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Hired", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_invalid_transition_applied_to_offer(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Offer", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_invalid_transition_hired_to_anything(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Hired")

        for target_status in VALID_STATUSES:
            if target_status == "Hired":
                continue
            response = await admin_client.post(
                f"/applications/{application.id}/status",
                data={"status": target_status, "notes": ""},
                follow_redirects=False,
            )
            assert response.status_code == 400, (
                f"Expected 400 for transition Hired -> {target_status}, got {response.status_code}"
            )

    async def test_invalid_transition_rejected_to_anything(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Rejected")

        for target_status in VALID_STATUSES:
            if target_status == "Rejected":
                continue
            response = await admin_client.post(
                f"/applications/{application.id}/status",
                data={"status": target_status, "notes": ""},
                follow_redirects=False,
            )
            assert response.status_code == 400, (
                f"Expected 400 for transition Rejected -> {target_status}, got {response.status_code}"
            )

    async def test_invalid_transition_withdrawn_to_anything(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Withdrawn")

        for target_status in VALID_STATUSES:
            if target_status == "Withdrawn":
                continue
            response = await admin_client.post(
                f"/applications/{application.id}/status",
                data={"status": target_status, "notes": ""},
                follow_redirects=False,
            )
            assert response.status_code == 400, (
                f"Expected 400 for transition Withdrawn -> {target_status}, got {response.status_code}"
            )

    async def test_invalid_status_value_rejected(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id, status="Applied")

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "InvalidStatus", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code in (400, 422)

    async def test_status_update_nonexistent_application(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            "/applications/nonexistent-id/status",
            data={"status": "Screening", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code in (302, 400)


class TestApplicationDetail:
    """Tests for application detail view."""

    async def test_application_detail_page_loads(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get(f"/applications/{application.id}")

        assert response.status_code == 200
        assert "Application" in response.text

    async def test_application_detail_nonexistent_returns_404(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await admin_client.get("/applications/nonexistent-id")

        assert response.status_code == 404

    async def test_application_detail_shows_candidate_info(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="detail-test@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get(f"/applications/{application.id}")

        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text

    async def test_application_detail_shows_job_info(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="jobinfo-test@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get(f"/applications/{application.id}")

        assert response.status_code == 200
        assert "Test Software Engineer" in response.text


class TestApplicationList:
    """Tests for application list view."""

    async def test_list_applications_page_loads(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await admin_client.get("/applications")
        assert response.status_code == 200

    async def test_list_applications_shows_created_application(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="list-test@example.com")
        await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get("/applications")

        assert response.status_code == 200
        assert "Jane" in response.text or "Doe" in response.text

    async def test_list_applications_filter_by_status(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate1 = await _create_candidate(db_session, email="filter1@example.com")
        candidate2 = await _create_candidate(db_session, email="filter2@example.com")
        await _create_application(db_session, job.id, candidate1.id, status="Applied")
        await _create_application(db_session, job.id, candidate2.id, status="Screening")

        response = await admin_client.get("/applications?status=Applied")

        assert response.status_code == 200

    async def test_list_applications_filter_by_job_id(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="filterjob@example.com")
        await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get(f"/applications?job_id={job.id}")

        assert response.status_code == 200


class TestKanbanPipelineView:
    """Tests for the kanban/pipeline view."""

    async def test_pipeline_view_loads(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await admin_client.get("/applications/pipeline")
        assert response.status_code == 200
        assert "Pipeline" in response.text or "pipeline" in response.text.lower()

    async def test_pipeline_view_groups_by_status(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate1 = await _create_candidate(db_session, email="kanban1@example.com")
        candidate2 = await _create_candidate(db_session, email="kanban2@example.com")
        candidate3 = await _create_candidate(db_session, email="kanban3@example.com")

        await _create_application(db_session, job.id, candidate1.id, status="Applied")
        await _create_application(db_session, job.id, candidate2.id, status="Screening")
        await _create_application(db_session, job.id, candidate3.id, status="Interview")

        response = await admin_client.get("/applications/pipeline")

        assert response.status_code == 200
        assert "Applied" in response.text
        assert "Screening" in response.text
        assert "Interview" in response.text

    async def test_pipeline_view_filter_by_job(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="kanban-filter@example.com")
        await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.get(f"/applications/pipeline?job_id={job.id}")

        assert response.status_code == 200

    async def test_pipeline_view_empty_state(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await admin_client.get("/applications/pipeline")
        assert response.status_code == 200


class TestApplicationRBAC:
    """Tests for role-based access control on application operations."""

    async def test_unauthenticated_user_redirected_from_list(
        self,
        unauthenticated_client: AsyncClient,
    ):
        response = await unauthenticated_client.get(
            "/applications",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    async def test_unauthenticated_user_redirected_from_detail(
        self,
        unauthenticated_client: AsyncClient,
    ):
        response = await unauthenticated_client.get(
            "/applications/some-id",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    async def test_unauthenticated_user_redirected_from_pipeline(
        self,
        unauthenticated_client: AsyncClient,
    ):
        response = await unauthenticated_client.get(
            "/applications/pipeline",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    async def test_interviewer_cannot_create_application(
        self,
        interviewer_client: AsyncClient,
        interviewer_user,
        db_session: AsyncSession,
    ):
        response = await interviewer_client.get(
            "/applications/new",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_update_status(
        self,
        interviewer_client: AsyncClient,
        interviewer_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-interviewer@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await interviewer_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Screening", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 403

    async def test_viewer_cannot_create_application(
        self,
        viewer_client: AsyncClient,
        viewer_user,
        db_session: AsyncSession,
    ):
        response = await viewer_client.get(
            "/applications/new",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_viewer_cannot_update_status(
        self,
        viewer_client: AsyncClient,
        viewer_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-viewer@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await viewer_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Screening", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 403

    async def test_admin_can_create_application(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-admin-create@example.com")

        response = await admin_client.post(
            "/applications/new",
            data={
                "job_id": job.id,
                "candidate_id": candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "source": "Direct",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_admin_can_update_status(
        self,
        admin_client: AsyncClient,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-admin-status@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await admin_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Screening", "notes": "Admin moving to screening"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_recruiter_can_create_application(
        self,
        recruiter_client: AsyncClient,
        recruiter_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-recruiter-create@example.com")

        response = await recruiter_client.post(
            "/applications/new",
            data={
                "job_id": job.id,
                "candidate_id": candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "source": "Referral",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_recruiter_can_update_status(
        self,
        recruiter_client: AsyncClient,
        recruiter_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-recruiter-status@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await recruiter_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Screening", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_hiring_manager_can_create_application(
        self,
        hiring_manager_client: AsyncClient,
        hiring_manager_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-hm-create@example.com")

        response = await hiring_manager_client.post(
            "/applications/new",
            data={
                "job_id": job.id,
                "candidate_id": candidate.id,
                "cover_letter": "",
                "resume_url": "",
                "source": "Direct",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_hiring_manager_can_update_status(
        self,
        hiring_manager_client: AsyncClient,
        hiring_manager_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-hm-status@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await hiring_manager_client.post(
            f"/applications/{application.id}/status",
            data={"status": "Screening", "notes": ""},
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_interviewer_can_view_application_list(
        self,
        interviewer_client: AsyncClient,
        interviewer_user,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await interviewer_client.get("/applications")
        assert response.status_code == 200

    async def test_interviewer_can_view_application_detail(
        self,
        interviewer_client: AsyncClient,
        interviewer_user,
        admin_user,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, created_by=admin_user.id)
        candidate = await _create_candidate(db_session, email="rbac-int-detail@example.com")
        application = await _create_application(db_session, job.id, candidate.id)

        response = await interviewer_client.get(f"/applications/{application.id}")
        assert response.status_code == 200

    async def test_interviewer_can_view_pipeline(
        self,
        interviewer_client: AsyncClient,
        interviewer_user,
        admin_user,
        db_session: AsyncSession,
    ):
        response = await interviewer_client.get("/applications/pipeline")
        assert response.status_code == 200


class TestApplicationServiceTransitions:
    """Tests verifying the ALLOWED_TRANSITIONS map is comprehensive and correct."""

    async def test_each_status_has_defined_transitions(self):
        """Every valid status must have an entry in ALLOWED_TRANSITIONS."""
        for status in VALID_STATUSES:
            assert status in ALLOWED_TRANSITIONS
            assert isinstance(ALLOWED_TRANSITIONS[status], list)

    async def test_all_transition_targets_are_valid_statuses(self):
        """Every target status in ALLOWED_TRANSITIONS must be a valid status."""
        for source_status, targets in ALLOWED_TRANSITIONS.items():
            for target in targets:
                assert target in VALID_STATUSES, (
                    f"Transition target '{target}' from '{source_status}' is not a valid status"
                )

    async def test_no_self_transitions(self):
        """No status should transition to itself."""
        for status, targets in ALLOWED_TRANSITIONS.items():
            assert status not in targets, (
                f"Status '{status}' has a self-transition which should not be allowed"
            )

    async def test_applied_transitions(self):
        """Applied should transition to Screening, Rejected, or Withdrawn."""
        expected = {"Screening", "Rejected", "Withdrawn"}
        actual = set(ALLOWED_TRANSITIONS["Applied"])
        assert actual == expected

    async def test_screening_transitions(self):
        """Screening should transition to Interview, Rejected, or Withdrawn."""
        expected = {"Interview", "Rejected", "Withdrawn"}
        actual = set(ALLOWED_TRANSITIONS["Screening"])
        assert actual == expected

    async def test_offer_transitions(self):
        """Offer should transition to Hired, Rejected, or Withdrawn."""
        expected = {"Hired", "Rejected", "Withdrawn"}
        actual = set(ALLOWED_TRANSITIONS["Offer"])
        assert actual == expected