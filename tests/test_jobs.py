import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User


class TestJobList:
    """Tests for the job listing page."""

    async def test_list_jobs_authenticated(self, admin_client: AsyncClient):
        """Authenticated users can view the jobs list page."""
        response = await admin_client.get("/jobs")
        assert response.status_code == 200
        assert "Job Requisitions" in response.text

    async def test_list_jobs_unauthenticated_can_view(self, unauthenticated_client: AsyncClient):
        """Unauthenticated users can still view the jobs list page."""
        response = await unauthenticated_client.get("/jobs")
        assert response.status_code == 200
        assert "Job Requisitions" in response.text

    async def test_list_jobs_empty(self, admin_client: AsyncClient):
        """Jobs list shows empty state when no jobs exist."""
        response = await admin_client.get("/jobs")
        assert response.status_code == 200
        assert "No jobs found" in response.text

    async def test_list_jobs_with_data(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Jobs list shows existing jobs."""
        job = Job(
            title="Software Engineer",
            department="Engineering",
            location="Remote",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()

        response = await admin_client.get("/jobs")
        assert response.status_code == 200
        assert "Software Engineer" in response.text

    async def test_list_jobs_filter_by_status(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Jobs list can be filtered by status."""
        job_open = Job(
            title="Open Position",
            status="Open",
            created_by=admin_user.id,
        )
        job_draft = Job(
            title="Draft Position",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job_open)
        db_session.add(job_draft)
        await db_session.flush()

        response = await admin_client.get("/jobs?status=Open")
        assert response.status_code == 200
        assert "Open Position" in response.text
        assert "Draft Position" not in response.text

    async def test_list_jobs_filter_by_department(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Jobs list can be filtered by department."""
        job_eng = Job(
            title="Engineer Role",
            department="Engineering",
            status="Open",
            created_by=admin_user.id,
        )
        job_mkt = Job(
            title="Marketing Role",
            department="Marketing",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job_eng)
        db_session.add(job_mkt)
        await db_session.flush()

        response = await admin_client.get("/jobs?department=Engineering")
        assert response.status_code == 200
        assert "Engineer Role" in response.text
        assert "Marketing Role" not in response.text

    async def test_list_jobs_search(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Jobs list can be searched by title."""
        job1 = Job(
            title="Python Developer",
            status="Open",
            created_by=admin_user.id,
        )
        job2 = Job(
            title="Java Developer",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job1)
        db_session.add(job2)
        await db_session.flush()

        response = await admin_client.get("/jobs?search=Python")
        assert response.status_code == 200
        assert "Python Developer" in response.text
        assert "Java Developer" not in response.text


class TestJobCreate:
    """Tests for job creation."""

    async def test_create_job_form_admin(self, admin_client: AsyncClient):
        """Admin can access the create job form."""
        response = await admin_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create New Job" in response.text

    async def test_create_job_form_hiring_manager(self, hiring_manager_client: AsyncClient):
        """Hiring Manager can access the create job form."""
        response = await hiring_manager_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create New Job" in response.text

    async def test_create_job_form_recruiter(self, recruiter_client: AsyncClient):
        """Recruiter can access the create job form."""
        response = await recruiter_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create New Job" in response.text

    async def test_create_job_form_interviewer_forbidden(self, interviewer_client: AsyncClient):
        """Interviewer cannot access the create job form."""
        response = await interviewer_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 403

    async def test_create_job_form_viewer_forbidden(self, viewer_client: AsyncClient):
        """Viewer cannot access the create job form."""
        response = await viewer_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 403

    async def test_create_job_success(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Admin can create a job successfully."""
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Senior Backend Engineer",
                "department": "Engineering",
                "location": "San Francisco, CA",
                "job_type": "Full-Time",
                "experience_level": "Senior",
                "is_remote": "true",
                "openings": "2",
                "salary_min": "150000",
                "salary_max": "200000",
                "salary_currency": "USD",
                "description": "We are looking for a senior backend engineer.",
                "requirements": "5+ years of experience",
                "responsibilities": "Design and build APIs",
                "benefits": "Health insurance, 401k",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Job).where(Job.title == "Senior Backend Engineer")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.department == "Engineering"
        assert job.location == "San Francisco, CA"
        assert job.job_type == "Full-Time"
        assert job.experience_level == "Senior"
        assert job.is_remote is True
        assert job.openings == 2
        assert job.salary_min == 150000.0
        assert job.salary_max == 200000.0
        assert job.status == "Draft"

    async def test_create_job_minimal_fields(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Job can be created with only the required title field."""
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Minimal Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Job).where(Job.title == "Minimal Job")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"

    async def test_create_job_unauthenticated_redirects(
        self,
        unauthenticated_client: AsyncClient,
    ):
        """Unauthenticated users cannot create jobs."""
        response = await unauthenticated_client.post(
            "/jobs/create",
            data={"title": "Test Job"},
            follow_redirects=False,
        )
        assert response.status_code in (401, 403)

    async def test_create_job_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
    ):
        """Interviewers cannot create jobs."""
        response = await interviewer_client.post(
            "/jobs/create",
            data={
                "title": "Forbidden Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403


class TestJobDetail:
    """Tests for job detail page."""

    async def test_job_detail_exists(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Job detail page renders for an existing job."""
        job = Job(
            title="Detail Test Job",
            department="Engineering",
            location="NYC",
            status="Open",
            description="A test job description.",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.get(f"/jobs/{job.id}")
        assert response.status_code == 200
        assert "Detail Test Job" in response.text
        assert "A test job description." in response.text

    async def test_job_detail_not_found(self, admin_client: AsyncClient):
        """Job detail page returns 404 for non-existent job."""
        response = await admin_client.get("/jobs/nonexistent-id-12345")
        assert response.status_code == 404
        assert "Job not found" in response.text

    async def test_job_detail_shows_applications(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Job detail page shows the applications section."""
        job = Job(
            title="Job With Apps Section",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.get(f"/jobs/{job.id}")
        assert response.status_code == 200
        assert "Applications" in response.text


class TestJobEdit:
    """Tests for job editing."""

    async def test_edit_job_form_admin(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Admin can access the edit job form."""
        job = Job(
            title="Editable Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.get(f"/jobs/{job.id}/edit")
        assert response.status_code == 200
        assert "Editable Job" in response.text

    async def test_edit_job_form_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Interviewer cannot access the edit job form."""
        job = Job(
            title="Restricted Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await interviewer_client.get(
            f"/jobs/{job.id}/edit",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_edit_job_submit(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Admin can update a job successfully."""
        job = Job(
            title="Original Title",
            department="Engineering",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/edit",
            data={
                "title": "Updated Title",
                "department": "Product",
                "location": "Remote",
                "job_type": "Full-Time",
                "experience_level": "Mid",
                "is_remote": "true",
                "openings": "3",
                "salary_min": "100000",
                "salary_max": "150000",
                "salary_currency": "USD",
                "description": "Updated description",
                "requirements": "Updated requirements",
                "responsibilities": "Updated responsibilities",
                "benefits": "Updated benefits",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.title == "Updated Title"
        assert job.department == "Product"

    async def test_edit_nonexistent_job_redirects(
        self,
        admin_client: AsyncClient,
    ):
        """Editing a non-existent job redirects to jobs list."""
        response = await admin_client.get(
            "/jobs/nonexistent-id-99999/edit",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/jobs" in response.headers.get("location", "")


class TestJobStatusTransitions:
    """Tests for job status transitions (Draft → Open → On Hold → Closed, etc.)."""

    async def test_draft_to_open(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """A Draft job can be published (transitioned to Open)."""
        job = Job(
            title="Draft to Open Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Open"

    async def test_open_to_on_hold(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """An Open job can be put On Hold."""
        job = Job(
            title="Open to Hold Job",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "On Hold"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "On Hold"

    async def test_open_to_closed(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """An Open job can be Closed."""
        job = Job(
            title="Open to Closed Job",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Closed"

    async def test_on_hold_to_open(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """An On Hold job can be reopened (transitioned to Open)."""
        job = Job(
            title="Hold to Open Job",
            status="On Hold",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Open"

    async def test_draft_to_cancelled(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """A Draft job can be Cancelled."""
        job = Job(
            title="Draft to Cancelled Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Cancelled"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Cancelled"

    async def test_closed_to_open(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """A Closed job can be reopened (transitioned to Open)."""
        job = Job(
            title="Closed to Open Job",
            status="Closed",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Open"

    async def test_invalid_transition_cancelled_to_open(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """A Cancelled job cannot be transitioned to Open (no allowed transitions)."""
        job = Job(
            title="Cancelled Job",
            status="Cancelled",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        # The route redirects back to the job detail on failure
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Cancelled"

    async def test_invalid_transition_draft_to_closed(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """A Draft job cannot be directly Closed (must go through Open first)."""
        job = Job(
            title="Draft Cannot Close",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Draft"

    async def test_status_update_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Interviewer cannot update job status."""
        job = Job(
            title="Interviewer Cannot Update",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await interviewer_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_status_update_viewer_forbidden(
        self,
        viewer_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Viewer cannot update job status."""
        job = Job(
            title="Viewer Cannot Update",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await viewer_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 403


class TestHiringManagerAssignment:
    """Tests for hiring manager assignment to jobs."""

    async def test_assign_hiring_manager_on_create(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        hiring_manager_user: User,
    ):
        """A hiring manager can be assigned when creating a job."""
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Job With HM",
                "department": "Engineering",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": hiring_manager_user.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Job).where(Job.title == "Job With HM")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.created_by == hiring_manager_user.id

    async def test_assign_hiring_manager_on_edit(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
        hiring_manager_user: User,
    ):
        """A hiring manager can be reassigned when editing a job."""
        job = Job(
            title="Reassign HM Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        assert job.created_by == admin_user.id

        response = await admin_client.post(
            f"/jobs/{job.id}/edit",
            data={
                "title": "Reassign HM Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": hiring_manager_user.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.created_by == hiring_manager_user.id

    async def test_job_detail_shows_hiring_manager(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        """Job detail page shows the assigned hiring manager."""
        job = Job(
            title="HM Display Job",
            status="Open",
            created_by=hiring_manager_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await admin_client.get(f"/jobs/{job.id}")
        assert response.status_code == 200
        assert hiring_manager_user.username in response.text


class TestPublishedJobsPublicBoard:
    """Tests for published jobs on the public landing page."""

    async def test_landing_page_shows_open_jobs(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """The landing page shows Open (published) jobs."""
        job = Job(
            title="Published Frontend Role",
            department="Engineering",
            location="Remote",
            status="Open",
            description="A great frontend role.",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()

        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Published Frontend Role" in response.text

    async def test_landing_page_hides_draft_jobs(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """The landing page does not show Draft jobs."""
        job = Job(
            title="Secret Draft Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()

        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Secret Draft Job" not in response.text

    async def test_landing_page_hides_closed_jobs(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """The landing page does not show Closed jobs."""
        job = Job(
            title="Closed Position",
            status="Closed",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()

        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Closed Position" not in response.text

    async def test_landing_page_hides_cancelled_jobs(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """The landing page does not show Cancelled jobs."""
        job = Job(
            title="Cancelled Position",
            status="Cancelled",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()

        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Cancelled Position" not in response.text

    async def test_landing_page_shows_only_open_among_mixed(
        self,
        unauthenticated_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Among mixed statuses, only Open jobs appear on the landing page."""
        jobs_data = [
            ("Open Job A", "Open"),
            ("Draft Job B", "Draft"),
            ("Closed Job C", "Closed"),
            ("On Hold Job D", "On Hold"),
            ("Open Job E", "Open"),
        ]
        for title, status in jobs_data:
            db_session.add(Job(
                title=title,
                status=status,
                created_by=admin_user.id,
            ))
        await db_session.flush()

        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Open Job A" in response.text
        assert "Open Job E" in response.text
        assert "Draft Job B" not in response.text
        assert "Closed Job C" not in response.text
        assert "On Hold Job D" not in response.text


class TestJobRBAC:
    """Tests for role-based access control on job operations."""

    async def test_hiring_manager_can_create_job(
        self,
        hiring_manager_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Hiring Manager can create a job."""
        response = await hiring_manager_client.post(
            "/jobs/create",
            data={
                "title": "HM Created Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Job).where(Job.title == "HM Created Job")
        )
        assert result.scalar_one_or_none() is not None

    async def test_recruiter_can_create_job(
        self,
        recruiter_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Recruiter can create a job."""
        response = await recruiter_client.post(
            "/jobs/create",
            data={
                "title": "Recruiter Created Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Job).where(Job.title == "Recruiter Created Job")
        )
        assert result.scalar_one_or_none() is not None

    async def test_recruiter_can_update_status(
        self,
        recruiter_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Recruiter can update job status."""
        job = Job(
            title="Recruiter Status Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await recruiter_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Open"

    async def test_hiring_manager_can_update_status(
        self,
        hiring_manager_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Hiring Manager can update job status."""
        job = Job(
            title="HM Status Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await hiring_manager_client.post(
            f"/jobs/{job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.status == "Open"

    async def test_hiring_manager_can_edit_job(
        self,
        hiring_manager_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Hiring Manager can edit a job."""
        job = Job(
            title="HM Edit Job",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await hiring_manager_client.post(
            f"/jobs/{job.id}/edit",
            data={
                "title": "HM Edited Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.refresh(job)
        assert job.title == "HM Edited Job"

    async def test_interviewer_cannot_edit_job(
        self,
        interviewer_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """Interviewer cannot edit a job."""
        job = Job(
            title="No Edit For Interviewer",
            status="Draft",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        response = await interviewer_client.post(
            f"/jobs/{job.id}/edit",
            data={
                "title": "Attempted Edit",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_viewer_cannot_create_job(
        self,
        viewer_client: AsyncClient,
    ):
        """Viewer cannot create a job."""
        response = await viewer_client.post(
            "/jobs/create",
            data={
                "title": "Viewer Job",
                "department": "",
                "location": "",
                "job_type": "",
                "experience_level": "",
                "is_remote": "",
                "openings": "1",
                "salary_currency": "USD",
                "description": "",
                "requirements": "",
                "responsibilities": "",
                "benefits": "",
                "status": "Draft",
                "hiring_manager_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_all_authenticated_roles_can_view_jobs(
        self,
        admin_client: AsyncClient,
        hiring_manager_client: AsyncClient,
        recruiter_client: AsyncClient,
        interviewer_client: AsyncClient,
        viewer_client: AsyncClient,
    ):
        """All authenticated roles can view the jobs list."""
        for client in [
            admin_client,
            hiring_manager_client,
            recruiter_client,
            interviewer_client,
            viewer_client,
        ]:
            response = await client.get("/jobs")
            assert response.status_code == 200

    async def test_all_authenticated_roles_can_view_job_detail(
        self,
        admin_client: AsyncClient,
        hiring_manager_client: AsyncClient,
        recruiter_client: AsyncClient,
        interviewer_client: AsyncClient,
        viewer_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        """All authenticated roles can view a job detail page."""
        job = Job(
            title="Viewable By All",
            status="Open",
            created_by=admin_user.id,
        )
        db_session.add(job)
        await db_session.flush()
        await db_session.refresh(job)

        for client in [
            admin_client,
            hiring_manager_client,
            recruiter_client,
            interviewer_client,
            viewer_client,
        ]:
            response = await client.get(f"/jobs/{job.id}")
            assert response.status_code == 200
            assert "Viewable By All" in response.text