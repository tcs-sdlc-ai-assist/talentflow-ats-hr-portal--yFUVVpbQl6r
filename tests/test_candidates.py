import json
import logging
from typing import Optional

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, Skill, candidate_skills
from app.models.job import Job
from app.models.application import Application
from app.models.user import User


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_candidate(
    db: AsyncSession,
    first_name: str = "Jane",
    last_name: str = "Doe",
    email: str = "jane.doe@example.com",
    phone: Optional[str] = "+1-555-0100",
    headline: Optional[str] = "Senior Engineer",
    summary: Optional[str] = "Experienced developer",
    location: Optional[str] = "San Francisco, CA",
    source: Optional[str] = "LinkedIn",
) -> Candidate:
    candidate = Candidate(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        headline=headline,
        summary=summary,
        location=location,
        source=source,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    return candidate


async def _create_skill(
    db: AsyncSession,
    name: str = "Python",
    years_of_experience: Optional[int] = 5,
) -> Skill:
    skill = Skill(name=name, years_of_experience=years_of_experience)
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return skill


async def _create_job(
    db: AsyncSession,
    title: str = "Software Engineer",
    status: str = "Open",
    created_by: Optional[str] = None,
) -> Job:
    job = Job(
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


async def _create_application(
    db: AsyncSession,
    job_id: str,
    candidate_id: str,
    status: str = "Applied",
) -> Application:
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


# ---------------------------------------------------------------------------
# Tests: List Candidates
# ---------------------------------------------------------------------------


class TestListCandidates:
    """Tests for GET /candidates."""

    async def test_list_candidates_redirects_unauthenticated(
        self,
        unauthenticated_client: httpx.AsyncClient,
    ):
        response = await unauthenticated_client.get(
            "/candidates", follow_redirects=False
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    async def test_list_candidates_empty(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/candidates")
        assert response.status_code == 200
        assert b"No candidates found" in response.content

    async def test_list_candidates_with_data(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(db_session, email="alice@example.com", first_name="Alice", last_name="Smith")
        await _create_candidate(db_session, email="bob@example.com", first_name="Bob", last_name="Jones")
        await db_session.commit()

        response = await admin_client.get("/candidates")
        assert response.status_code == 200
        assert b"Alice" in response.content
        assert b"Bob" in response.content

    async def test_list_candidates_search_filter(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(db_session, email="alice@example.com", first_name="Alice", last_name="Smith")
        await _create_candidate(db_session, email="bob@example.com", first_name="Bob", last_name="Jones")
        await db_session.commit()

        response = await admin_client.get("/candidates?search=Alice")
        assert response.status_code == 200
        assert b"Alice" in response.content
        assert b"Bob" not in response.content

    async def test_list_candidates_location_filter(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(
            db_session, email="sf@example.com", first_name="SF", last_name="Person", location="San Francisco"
        )
        await _create_candidate(
            db_session, email="ny@example.com", first_name="NY", last_name="Person", location="New York"
        )
        await db_session.commit()

        response = await admin_client.get("/candidates?location=San+Francisco")
        assert response.status_code == 200
        assert b"SF" in response.content
        assert b"NY" not in response.content

    async def test_list_candidates_source_filter(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(
            db_session, email="li@example.com", first_name="Li", last_name="User", source="LinkedIn"
        )
        await _create_candidate(
            db_session, email="ref@example.com", first_name="Ref", last_name="User", source="Referral"
        )
        await db_session.commit()

        response = await admin_client.get("/candidates?source=LinkedIn")
        assert response.status_code == 200
        assert b"Li" in response.content

    async def test_list_candidates_viewer_can_view(
        self,
        viewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(db_session, email="viewer-test@example.com", first_name="ViewTest", last_name="User")
        await db_session.commit()

        response = await viewer_client.get("/candidates")
        assert response.status_code == 200
        assert b"ViewTest" in response.content


# ---------------------------------------------------------------------------
# Tests: Create Candidate
# ---------------------------------------------------------------------------


class TestCreateCandidate:
    """Tests for GET/POST /candidates/create."""

    async def test_create_form_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/candidates/create")
        assert response.status_code == 200
        assert b"Add New Candidate" in response.content or b"New Candidate" in response.content

    async def test_create_form_accessible_by_recruiter(
        self,
        recruiter_client: httpx.AsyncClient,
    ):
        response = await recruiter_client.get("/candidates/create")
        assert response.status_code == 200

    async def test_create_form_forbidden_for_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get("/candidates/create")
        assert response.status_code == 403

    async def test_create_form_forbidden_for_viewer(
        self,
        viewer_client: httpx.AsyncClient,
    ):
        response = await viewer_client.get("/candidates/create")
        assert response.status_code == 403

    async def test_create_candidate_success(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "New",
                "last_name": "Candidate",
                "email": "new.candidate@example.com",
                "phone": "+1-555-0199",
                "headline": "Full Stack Developer",
                "summary": "Great developer",
                "location": "Austin, TX",
                "source": "Direct",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/candidates/" in response.headers["location"]

    async def test_create_candidate_with_skills(
        self,
        admin_client: httpx.AsyncClient,
    ):
        skills_json = json.dumps([
            {"name": "Python", "years_of_experience": 5},
            {"name": "JavaScript", "years_of_experience": 3},
        ])
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Skilled",
                "last_name": "Dev",
                "email": "skilled.dev@example.com",
                "skills_json": skills_json,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_candidate_duplicate_email_fails(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        await _create_candidate(db_session, email="dup@example.com")
        await db_session.commit()

        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Dup",
                "last_name": "User",
                "email": "dup@example.com",
            },
        )
        assert response.status_code == 400
        assert b"already exists" in response.content

    async def test_create_candidate_recruiter_allowed(
        self,
        recruiter_client: httpx.AsyncClient,
    ):
        response = await recruiter_client.post(
            "/candidates/create",
            data={
                "first_name": "Recruiter",
                "last_name": "Created",
                "email": "recruiter.created@example.com",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_create_candidate_interviewer_forbidden(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.post(
            "/candidates/create",
            data={
                "first_name": "Blocked",
                "last_name": "User",
                "email": "blocked@example.com",
            },
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: Candidate Detail
# ---------------------------------------------------------------------------


class TestCandidateDetail:
    """Tests for GET /candidates/{candidate_id}."""

    async def test_detail_page_renders(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="detail@example.com", first_name="Detail", last_name="Test")
        await db_session.commit()

        response = await admin_client.get(f"/candidates/{candidate.id}")
        assert response.status_code == 200
        assert b"Detail" in response.content
        assert b"Test" in response.content

    async def test_detail_page_not_found(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/candidates/nonexistent-id-12345")
        assert response.status_code == 404

    async def test_detail_page_shows_skills(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="skillshow@example.com", first_name="Skill", last_name="Show")
        skill = await _create_skill(db_session, name="React", years_of_experience=3)
        candidate.skills.append(skill)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.get(f"/candidates/{candidate.id}")
        assert response.status_code == 200
        assert b"React" in response.content

    async def test_detail_page_redirects_unauthenticated(
        self,
        unauthenticated_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="unauth-detail@example.com")
        await db_session.commit()

        response = await unauthenticated_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    async def test_detail_page_viewer_can_view(
        self,
        viewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="viewer-detail@example.com", first_name="ViewerDetail")
        await db_session.commit()

        response = await viewer_client.get(f"/candidates/{candidate.id}")
        assert response.status_code == 200
        assert b"ViewerDetail" in response.content


# ---------------------------------------------------------------------------
# Tests: Edit Candidate
# ---------------------------------------------------------------------------


class TestEditCandidate:
    """Tests for GET/POST /candidates/{candidate_id}/edit."""

    async def test_edit_form_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="edit-form@example.com")
        await db_session.commit()

        response = await admin_client.get(f"/candidates/{candidate.id}/edit")
        assert response.status_code == 200

    async def test_edit_form_forbidden_for_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="edit-forbidden@example.com")
        await db_session.commit()

        response = await interviewer_client.get(f"/candidates/{candidate.id}/edit")
        assert response.status_code == 403

    async def test_edit_form_forbidden_for_viewer(
        self,
        viewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="edit-viewer@example.com")
        await db_session.commit()

        response = await viewer_client.get(f"/candidates/{candidate.id}/edit")
        assert response.status_code == 403

    async def test_edit_candidate_success(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(
            db_session, email="edit-success@example.com", first_name="Before", last_name="Edit"
        )
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "After",
                "last_name": "Edit",
                "email": "edit-success@example.com",
                "headline": "Updated Headline",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{candidate.id}" in response.headers["location"]

    async def test_edit_candidate_update_skills(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="edit-skills@example.com")
        await db_session.commit()

        skills_json = json.dumps([
            {"name": "Go", "years_of_experience": 2},
            {"name": "Rust", "years_of_experience": 1},
        ])
        response = await admin_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "email": candidate.email,
                "skills_json": skills_json,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_edit_candidate_nonexistent_redirects(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get(
            "/candidates/nonexistent-id-99999/edit",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/candidates" in response.headers["location"]

    async def test_edit_candidate_duplicate_email_fails(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate1 = await _create_candidate(db_session, email="first@example.com", first_name="First")
        candidate2 = await _create_candidate(db_session, email="second@example.com", first_name="Second")
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate2.id}/edit",
            data={
                "first_name": "Second",
                "last_name": "User",
                "email": "first@example.com",
            },
        )
        assert response.status_code == 400
        assert b"already exists" in response.content

    async def test_edit_candidate_hiring_manager_allowed(
        self,
        hiring_manager_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="hm-edit@example.com")
        await db_session.commit()

        response = await hiring_manager_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "HM",
                "last_name": "Edited",
                "email": "hm-edit@example.com",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Tests: Skill Management (Many-to-Many)
# ---------------------------------------------------------------------------


class TestSkillManagement:
    """Tests for POST /candidates/{id}/skills and /candidates/{id}/skills/{name}/delete."""

    async def test_add_skill_to_candidate(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="add-skill@example.com")
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={
                "skill_name": "Python",
                "years_of_experience": "5",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{candidate.id}" in response.headers["location"]

    async def test_add_skill_without_years(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="skill-noyears@example.com")
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={
                "skill_name": "Docker",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_add_duplicate_skill_updates_years(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="dup-skill@example.com")
        skill = await _create_skill(db_session, name="TypeScript", years_of_experience=2)
        candidate.skills.append(skill)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={
                "skill_name": "TypeScript",
                "years_of_experience": "4",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_remove_skill_from_candidate(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="remove-skill@example.com")
        skill = await _create_skill(db_session, name="Java", years_of_experience=3)
        candidate.skills.append(skill)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills/Java/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{candidate.id}" in response.headers["location"]

    async def test_remove_nonexistent_skill_redirects(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="remove-nonskill@example.com")
        await db_session.commit()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills/NonExistentSkill/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_add_skill_forbidden_for_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="skill-forbidden@example.com")
        await db_session.commit()

        response = await interviewer_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Blocked"},
        )
        assert response.status_code == 403

    async def test_remove_skill_forbidden_for_viewer(
        self,
        viewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="skill-viewer@example.com")
        await db_session.commit()

        response = await viewer_client.post(
            f"/candidates/{candidate.id}/skills/SomeSkill/delete",
        )
        assert response.status_code == 403

    async def test_add_skill_recruiter_allowed(
        self,
        recruiter_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        candidate = await _create_candidate(db_session, email="skill-recruiter@example.com")
        await db_session.commit()

        response = await recruiter_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Kubernetes"},
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Tests: Candidate Applications View
# ---------------------------------------------------------------------------


class TestCandidateApplicationsView:
    """Tests that