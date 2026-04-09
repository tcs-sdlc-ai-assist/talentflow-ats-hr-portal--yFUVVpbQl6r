import logging
from typing import Optional

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import _create_user, _make_authenticated_cookies, async_session_factory


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper: create a fresh client with cookies for a given user
# ---------------------------------------------------------------------------

async def _client_for_user(user: User) -> httpx.AsyncClient:
    from app.main import app

    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )
    client.cookies.update(_make_authenticated_cookies(user))
    return client


async def _anon_client() -> httpx.AsyncClient:
    from app.main import app

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


# ===========================================================================
# 1. Unauthenticated access → redirect to /auth/login (302)
# ===========================================================================


class TestUnauthenticatedAccess:
    """Unauthenticated users should be redirected to the login page for
    protected HTML routes, or receive 401 for API-only endpoints."""

    @pytest.mark.parametrize(
        "path",
        [
            "/dashboard",
            "/candidates",
            "/applications",
            "/interviews",
        ],
    )
    async def test_unauthenticated_html_routes_redirect_to_login(self, path: str):
        client = await _anon_client()
        try:
            resp = await client.get(path, follow_redirects=False)
            assert resp.status_code == 302
            location = resp.headers.get("location", "")
            assert "/auth/login" in location, (
                f"Expected redirect to /auth/login, got location={location}"
            )
        finally:
            await client.aclose()

    async def test_unauthenticated_dashboard_redirects(self):
        client = await _anon_client()
        try:
            resp = await client.get("/dashboard", follow_redirects=False)
            assert resp.status_code in (302, 401)
        finally:
            await client.aclose()

    async def test_unauthenticated_api_metrics_returns_401(self):
        client = await _anon_client()
        try:
            resp = await client.get("/api/dashboard/metrics", follow_redirects=False)
            assert resp.status_code in (401, 302)
        finally:
            await client.aclose()

    async def test_unauthenticated_audit_logs_denied(self):
        client = await _anon_client()
        try:
            resp = await client.get("/dashboard/audit-logs", follow_redirects=False)
            assert resp.status_code in (401, 302)
        finally:
            await client.aclose()


# ===========================================================================
# 2. Admin role — full access
# ===========================================================================


class TestAdminAccess:
    """Admin users should have access to all routes including audit logs."""

    async def test_admin_can_access_dashboard(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_jobs(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/jobs", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_candidates(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/candidates", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_applications(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/applications", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_interviews(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/interviews", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_audit_logs(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_api_audit_logs(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/api/audit-logs", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_create_job_form(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/jobs/create", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_create_candidate_form(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/candidates/create", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_new_application_form(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/applications/new", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_schedule_interview_form(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/interviews/schedule", follow_redirects=False)
        assert resp.status_code == 200

    async def test_admin_can_access_api_dashboard_metrics(self, admin_client: httpx.AsyncClient):
        resp = await admin_client.get("/api/dashboard/metrics", follow_redirects=False)
        assert resp.status_code == 200


# ===========================================================================
# 3. Hiring Manager role — permitted routes
# ===========================================================================


class TestHiringManagerAccess:
    """Hiring Managers can manage jobs, candidates, applications, interviews
    but NOT audit logs."""

    async def test_hm_can_access_dashboard(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200

    async def test_hm_can_access_jobs(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/jobs", follow_redirects=False)
        assert resp.status_code == 200

    async def test_hm_can_access_create_job(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/jobs/create", follow_redirects=False)
        assert resp.status_code == 200

    async def test_hm_can_access_candidates(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/candidates", follow_redirects=False)
        assert resp.status_code == 200

    async def test_hm_can_access_applications(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/applications", follow_redirects=False)
        assert resp.status_code == 200

    async def test_hm_can_access_interviews(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/interviews", follow_redirects=False)
        assert resp.status_code == 200

    async def test_hm_cannot_access_audit_logs(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert resp.status_code == 403

    async def test_hm_cannot_access_api_audit_logs(self, hiring_manager_client: httpx.AsyncClient):
        resp = await hiring_manager_client.get("/api/audit-logs", follow_redirects=False)
        assert resp.status_code == 403


# ===========================================================================
# 4. Recruiter role — permitted routes
# ===========================================================================


class TestRecruiterAccess:
    """Recruiters can manage candidates, applications, interviews, jobs
    but NOT audit logs."""

    async def test_recruiter_can_access_dashboard(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_jobs(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/jobs", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_create_job(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/jobs/create", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_candidates(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/candidates", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_create_candidate(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/candidates/create", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_applications(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/applications", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_new_application(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/applications/new", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_interviews(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/interviews", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_can_access_schedule_interview(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/interviews/schedule", follow_redirects=False)
        assert resp.status_code == 200

    async def test_recruiter_cannot_access_audit_logs(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert resp.status_code == 403

    async def test_recruiter_cannot_access_api_audit_logs(self, recruiter_client: httpx.AsyncClient):
        resp = await recruiter_client.get("/api/audit-logs", follow_redirects=False)
        assert resp.status_code == 403


# ===========================================================================
# 5. Interviewer role — limited access
# ===========================================================================


class TestInterviewerAccess:
    """Interviewers can view interviews and submit feedback but cannot
    create jobs, candidates, applications, or access audit logs."""

    async def test_interviewer_can_access_dashboard(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200

    async def test_interviewer_can_access_interviews(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/interviews", follow_redirects=False)
        assert resp.status_code == 200

    async def test_interviewer_can_access_my_interviews(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/interviews/my", follow_redirects=False)
        assert resp.status_code == 200

    async def test_interviewer_cannot_create_job(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/jobs/create", follow_redirects=False)
        assert resp.status_code == 403

    async def test_interviewer_cannot_create_candidate(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/candidates/create", follow_redirects=False)
        assert resp.status_code == 403

    async def test_interviewer_cannot_create_application(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/applications/new", follow_redirects=False)
        assert resp.status_code == 403

    async def test_interviewer_cannot_schedule_interview(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/interviews/schedule", follow_redirects=False)
        assert resp.status_code == 403

    async def test_interviewer_cannot_access_audit_logs(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert resp.status_code == 403

    async def test_interviewer_cannot_access_api_audit_logs(self, interviewer_client: httpx.AsyncClient):
        resp = await interviewer_client.get("/api/audit-logs", follow_redirects=False)
        assert resp.status_code == 403


# ===========================================================================
# 6. Viewer role — most restricted
# ===========================================================================


class TestViewerAccess:
    """Viewers have the most restricted access — they can view jobs and
    their own dashboard but cannot create or manage resources."""

    async def test_viewer_can_access_dashboard(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200

    async def test_viewer_can_view_jobs(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/jobs", follow_redirects=False)
        assert resp.status_code == 200

    async def test_viewer_cannot_create_job(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/jobs/create", follow_redirects=False)
        assert resp.status_code == 403

    async def test_viewer_cannot_create_candidate(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/candidates/create", follow_redirects=False)
        assert resp.status_code == 403

    async def test_viewer_cannot_create_application(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/applications/new", follow_redirects=False)
        assert resp.status_code == 403

    async def test_viewer_cannot_schedule_interview(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/interviews/schedule", follow_redirects=False)
        assert resp.status_code == 403

    async def test_viewer_cannot_access_audit_logs(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/dashboard/audit-logs", follow_redirects=False)
        assert resp.status_code == 403

    async def test_viewer_cannot_access_api_audit_logs(self, viewer_client: httpx.AsyncClient):
        resp = await viewer_client.get("/api/audit-logs", follow_redirects=False)
        assert resp.status_code == 403


# ===========================================================================
# 7. Role-specific dashboard content
# ===========================================================================


class TestRoleSpecificDashboardContent:
    """Each role should see role-appropriate content on the dashboard."""

    async def test_admin_dashboard_shows_pipeline_and_audit(
        self, admin_client: httpx.AsyncClient
    ):
        resp = await admin_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200
        body = resp.text
        assert "Pipeline Distribution" in body or "Recent Activity" in body

    async def test_hiring_manager_dashboard_shows_my_jobs(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        resp = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200
        body = resp.text
        assert "My Job Requisitions" in body or "My Open Jobs" in body

    async def test_interviewer_dashboard_shows_upcoming_interviews(
        self, interviewer_client: httpx.AsyncClient
    ):
        resp = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200
        body = resp.text
        assert "Upcoming Interviews" in body or "Pending Feedback" in body

    async def test_viewer_dashboard_shows_welcome(
        self, viewer_client: httpx.AsyncClient
    ):
        resp = await viewer_client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 200
        body = resp.text
        assert "Welcome to TalentFlow" in body or "Browse Jobs" in body


# ===========================================================================
# 8. POST routes — RBAC on write operations
# ===========================================================================


class TestWriteOperationRBAC:
    """Write operations (POST) should enforce role restrictions."""

    async def test_interviewer_cannot_post_create_job(
        self, interviewer_client: httpx.AsyncClient
    ):
        resp = await interviewer_client.post(
            "/jobs/create",
            data={"title": "Forbidden Job", "status": "Draft"},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_post_create_candidate(
        self, viewer_client: httpx.AsyncClient
    ):
        resp = await viewer_client.post(
            "/candidates/create",
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 403

    async def test_interviewer_cannot_post_create_application(
        self, interviewer_client: httpx.AsyncClient
    ):
        resp = await interviewer_client.post(
            "/applications/new",
            data={
                "job_id": "fake-job-id",
                "candidate_id": "fake-candidate-id",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_post_schedule_interview(
        self, viewer_client: httpx.AsyncClient
    ):
        resp = await viewer_client.post(
            "/interviews/schedule",
            data={
                "application_id": "fake-app-id",
                "interviewer_id": "fake-interviewer-id",
                "scheduled_at": "2025-12-01T10:00",
                "interview_type": "phone_screen",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 403

    async def test_admin_can_post_create_job(
        self, admin_client: httpx.AsyncClient
    ):
        resp = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Admin Created Job",
                "status": "Draft",
                "openings": "1",
            },
            follow_redirects=False,
        )
        # Should succeed — either 303 redirect or 200
        assert resp.status_code in (200, 302, 303)

    async def test_recruiter_can_post_create_candidate(
        self, recruiter_client: httpx.AsyncClient
    ):
        resp = await recruiter_client.post(
            "/candidates/create",
            data={
                "first_name": "Recruiter",
                "last_name": "Created",
                "email": "recruiter.created@example.com",
            },
            follow_redirects=False,
        )
        # Should succeed — either redirect to detail or 200
        assert resp.status_code in (200, 302, 303)


# ===========================================================================
# 9. Audit logging of unauthorized attempts (via log capture)
# ===========================================================================


class TestAuditLoggingOfUnauthorizedAttempts:
    """RBAC violations should be logged with appropriate warning messages."""

    async def test_rbac_violation_is_logged(
        self,
        interviewer_client: httpx.AsyncClient,
        caplog,
    ):
        with caplog.at_level(logging.WARNING, logger="app.middleware.auth_middleware"):
            resp = await interviewer_client.get(
                "/jobs/create", follow_redirects=False
            )
            assert resp.status_code == 403

        # Check that a RBAC violation warning was logged
        rbac_messages = [
            record
            for record in caplog.records
            if "RBAC violation" in record.message or "Access denied" in record.message
        ]
        assert len(rbac_messages) >= 1, (
            f"Expected RBAC violation log message, got: {[r.message for r in caplog.records]}"
        )

    async def test_rbac_violation_log_contains_user_info(
        self,
        viewer_client: httpx.AsyncClient,
        viewer_user: User,
        caplog,
    ):
        with caplog.at_level(logging.WARNING, logger="app.middleware.auth_middleware"):
            resp = await viewer_client.get(
                "/candidates/create", follow_redirects=False
            )
            assert resp.status_code == 403

        rbac_messages = [
            record
            for record in caplog.records
            if "RBAC violation" in record.message
        ]
        assert len(rbac_messages) >= 1

        log_text = rbac_messages[0].message
        assert viewer_user.username in log_text
        assert viewer_user.role in log_text

    async def test_unauthenticated_access_is_logged(
        self,
        caplog,
    ):
        client = await _anon_client()
        try:
            with caplog.at_level(logging.INFO, logger="app.middleware.auth_middleware"):
                resp = await client.get(
                    "/api/dashboard/metrics", follow_redirects=False
                )
                # Either 401 or redirect
                assert resp.status_code in (401, 302)

            if resp.status_code == 401:
                unauth_messages = [
                    record
                    for record in caplog.records
                    if "Unauthorized" in record.message or "unauthorized" in record.message.lower()
                ]
                assert len(unauth_messages) >= 1, (
                    f"Expected unauthorized access log, got: {[r.message for r in caplog.records]}"
                )
        finally:
            await client.aclose()


# ===========================================================================
# 10. Cross-role boundary tests — specific forbidden transitions
# ===========================================================================


class TestCrossRoleBoundaries:
    """Verify that specific role boundaries are enforced correctly."""

    async def test_only_admin_can_access_audit_logs_html(
        self,
        db_session: AsyncSession,
    ):
        """Iterate through non-admin roles and confirm audit logs are denied."""
        roles_denied = ["Hiring Manager", "Recruiter", "Interviewer", "Viewer"]

        for idx, role in enumerate(roles_denied):
            user = await _create_user(
                db=db_session,
                username=f"crossrole_{role.lower().replace(' ', '_')}_{idx}",
                password="testpass12345",
                role=role,
                full_name=f"Cross Role {role}",
            )
            client = await _client_for_user(user)
            try:
                resp = await client.get("/dashboard/audit-logs", follow_redirects=False)
                assert resp.status_code == 403, (
                    f"Role '{role}' should be denied audit log access, got {resp.status_code}"
                )
            finally:
                await client.aclose()

    async def test_only_privileged_roles_can_create_jobs(
        self,
        db_session: AsyncSession,
    ):
        """Only Admin, Hiring Manager, and Recruiter can access job creation."""
        allowed_roles = ["Admin", "Hiring Manager", "Recruiter"]
        denied_roles = ["Interviewer", "Viewer"]

        for idx, role in enumerate(allowed_roles):
            user = await _create_user(
                db=db_session,
                username=f"jobcreate_allowed_{idx}",
                password="testpass12345",
                role=role,
                full_name=f"Job Create {role}",
            )
            client = await _client_for_user(user)
            try:
                resp = await client.get("/jobs/create", follow_redirects=False)
                assert resp.status_code == 200, (
                    f"Role '{role}' should be allowed to create jobs, got {resp.status_code}"
                )
            finally:
                await client.aclose()

        for idx, role in enumerate(denied_roles):
            user = await _create_user(
                db=db_session,
                username=f"jobcreate_denied_{idx}",
                password="testpass12345",
                role=role,
                full_name=f"Job Create Denied {role}",
            )
            client = await _client_for_user(user)
            try:
                resp = await client.get("/jobs/create", follow_redirects=False)
                assert resp.status_code == 403, (
                    f"Role '{role}' should be denied job creation, got {resp.status_code}"
                )
            finally:
                await client.aclose()

    async def test_only_privileged_roles_can_create_candidates(
        self,
        db_session: AsyncSession,
    ):
        """Only Admin, Hiring Manager, and Recruiter can create candidates."""
        denied_roles = ["Interviewer", "Viewer"]

        for idx, role in enumerate(denied_roles):
            user = await _create_user(
                db=db_session,
                username=f"candcreate_denied_{idx}",
                password="testpass12345",
                role=role,
                full_name=f"Cand Create Denied {role}",
            )
            client = await _client_for_user(user)
            try:
                resp = await client.get("/candidates/create", follow_redirects=False)
                assert resp.status_code == 403, (
                    f"Role '{role}' should be denied candidate creation, got {resp.status_code}"
                )
            finally:
                await client.aclose()


# ===========================================================================
# 11. Health endpoint — public access (no auth required)
# ===========================================================================


class TestPublicEndpoints:
    """Public endpoints should be accessible without authentication."""

    async def test_health_endpoint_is_public(self):
        client = await _anon_client()
        try:
            resp = await client.get("/api/health", follow_redirects=False)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
        finally:
            await client.aclose()

    async def test_landing_page_is_public(self):
        client = await _anon_client()
        try:
            resp = await client.get("/", follow_redirects=False)
            assert resp.status_code == 200
            assert "TalentFlow" in resp.text
        finally:
            await client.aclose()

    async def test_login_page_is_public(self):
        client = await _anon_client()
        try:
            resp = await client.get("/auth/login", follow_redirects=False)
            assert resp.status_code == 200
        finally:
            await client.aclose()

    async def test_register_page_is_public(self):
        client = await _anon_client()
        try:
            resp = await client.get("/auth/register", follow_redirects=False)
            assert resp.status_code == 200
        finally:
            await client.aclose()


# ===========================================================================
# 12. 403 response detail message
# ===========================================================================


class TestForbiddenResponseDetail:
    """403 responses should include a meaningful error detail."""

    async def test_403_includes_role_info(
        self, interviewer_client: httpx.AsyncClient
    ):
        resp = await interviewer_client.get("/jobs/create", follow_redirects=False)
        assert resp.status_code == 403
        data = resp.json()
        assert "detail" in data
        assert "Interviewer" in data["detail"] or "Access denied" in data["detail"]

    async def test_403_includes_required_roles(
        self, viewer_client: httpx.AsyncClient
    ):
        resp = await viewer_client.get("/candidates/create", follow_redirects=False)
        assert resp.status_code == 403
        data = resp.json()
        assert "detail" in data
        detail = data["detail"]
        # The detail should mention at least one of the allowed roles
        assert any(
            role in detail
            for role in ["Admin", "Super Admin", "Recruiter", "Hiring Manager"]
        ), f"Expected allowed roles in detail, got: {detail}"