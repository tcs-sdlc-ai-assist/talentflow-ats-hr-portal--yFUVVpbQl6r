import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_auth, require_roles
from app.models.user import User
from app.services.candidate_service import CandidateService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/candidates")
async def list_candidates(
    request: Request,
    search: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    service = CandidateService(db)

    result = await service.list_candidates(
        search=search,
        skill=skill,
        location=location,
        source=source,
        page=page,
        page_size=page_size,
    )

    source_options = await service.get_source_options()

    filters = {
        "search": search or "",
        "skill": skill or "",
        "location": location or "",
        "source": source or "",
    }

    return templates.TemplateResponse(
        request,
        "candidates/list.html",
        context={
            "user": user,
            "candidates": result["items"],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
            "total_pages": result["total_pages"],
            "filters": filters,
            "source_options": source_options,
        },
    )


@router.get("/candidates/create")
async def create_candidate_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": user,
            "candidate": None,
        },
    )


@router.post("/candidates/create")
async def create_candidate(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    headline: Optional[str] = Form(None),
    summary: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    portfolio_url: Optional[str] = Form(None),
    resume_url: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    skills_json: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    service = CandidateService(db)

    skills = None
    if skills_json:
        try:
            parsed = json.loads(skills_json)
            if isinstance(parsed, list):
                skills = parsed
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid skills_json received: %s", skills_json)

    try:
        candidate = await service.create_candidate(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.strip(),
            phone=phone.strip() if phone else None,
            headline=headline.strip() if headline else None,
            summary=summary.strip() if summary else None,
            location=location.strip() if location else None,
            linkedin_url=linkedin_url.strip() if linkedin_url else None,
            portfolio_url=portfolio_url.strip() if portfolio_url else None,
            resume_url=resume_url.strip() if resume_url else None,
            source=source.strip() if source else None,
            skills=skills,
        )
        logger.info(
            "Candidate created: id=%s, email=%s, by user=%s",
            candidate.id,
            candidate.email,
            user.id,
        )
        return RedirectResponse(
            url=f"/candidates/{candidate.id}",
            status_code=302,
        )
    except ValueError as e:
        logger.warning("Failed to create candidate: %s", e)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": user,
                "candidate": None,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/candidates/{candidate_id}")
async def candidate_detail(
    request: Request,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    if user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    service = CandidateService(db)
    candidate = await service.get_candidate(candidate_id)

    if candidate is None:
        return templates.TemplateResponse(
            request,
            "candidates/list.html",
            context={
                "user": user,
                "candidates": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "total_pages": 0,
                "filters": {},
                "source_options": [],
                "error": f"Candidate with id '{candidate_id}' not found.",
            },
            status_code=404,
        )

    applications = []
    try:
        applications = await service.get_candidate_applications(candidate_id)
    except ValueError:
        pass

    return templates.TemplateResponse(
        request,
        "candidates/detail.html",
        context={
            "user": user,
            "candidate": candidate,
            "applications": applications,
        },
    )


@router.get("/candidates/{candidate_id}/edit")
async def edit_candidate_form(
    request: Request,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    service = CandidateService(db)
    candidate = await service.get_candidate(candidate_id)

    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=302)

    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": user,
            "candidate": candidate,
        },
    )


@router.post("/candidates/{candidate_id}/edit")
async def update_candidate(
    request: Request,
    candidate_id: str,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    headline: Optional[str] = Form(None),
    summary: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    portfolio_url: Optional[str] = Form(None),
    resume_url: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    skills_json: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    service = CandidateService(db)

    candidate = await service.get_candidate(candidate_id)
    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=302)

    skills = None
    if skills_json is not None:
        try:
            parsed = json.loads(skills_json)
            if isinstance(parsed, list):
                skills = parsed
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid skills_json received during update: %s", skills_json)

    try:
        updated_candidate = await service.update_candidate(
            candidate_id=candidate_id,
            first_name=first_name.strip() if first_name else None,
            last_name=last_name.strip() if last_name else None,
            email=email.strip() if email else None,
            phone=phone.strip() if phone else None,
            headline=headline.strip() if headline else None,
            summary=summary.strip() if summary else None,
            location=location.strip() if location else None,
            linkedin_url=linkedin_url.strip() if linkedin_url else None,
            portfolio_url=portfolio_url.strip() if portfolio_url else None,
            resume_url=resume_url.strip() if resume_url else None,
            source=source.strip() if source else None,
            skills=skills,
        )
        logger.info(
            "Candidate updated: id=%s, by user=%s",
            candidate_id,
            user.id,
        )
        return RedirectResponse(
            url=f"/candidates/{updated_candidate.id}",
            status_code=302,
        )
    except ValueError as e:
        logger.warning("Failed to update candidate %s: %s", candidate_id, e)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": user,
                "candidate": candidate,
                "error": str(e),
            },
            status_code=400,
        )


@router.post("/candidates/{candidate_id}/skills")
async def add_candidate_skill(
    request: Request,
    candidate_id: str,
    skill_name: str = Form(...),
    years_of_experience: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    service = CandidateService(db)

    years: Optional[int] = None
    if years_of_experience is not None and years_of_experience.strip():
        try:
            years = int(years_of_experience.strip())
            if years < 0:
                years = None
        except ValueError:
            years = None

    try:
        await service.add_skill(
            candidate_id=candidate_id,
            skill_name=skill_name.strip(),
            years_of_experience=years,
        )
        logger.info(
            "Skill '%s' added to candidate %s by user %s",
            skill_name.strip(),
            candidate_id,
            user.id,
        )
    except ValueError as e:
        logger.warning("Failed to add skill to candidate %s: %s", candidate_id, e)

    return RedirectResponse(
        url=f"/candidates/{candidate_id}",
        status_code=302,
    )


@router.post("/candidates/{candidate_id}/skills/{skill_name}/delete")
async def remove_candidate_skill(
    request: Request,
    candidate_id: str,
    skill_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    service = CandidateService(db)

    try:
        await service.remove_skill(
            candidate_id=candidate_id,
            skill_name=skill_name,
        )
        logger.info(
            "Skill '%s' removed from candidate %s by user %s",
            skill_name,
            candidate_id,
            user.id,
        )
    except ValueError as e:
        logger.warning(
            "Failed to remove skill '%s' from candidate %s: %s",
            skill_name,
            candidate_id,
            e,
        )

    return RedirectResponse(
        url=f"/candidates/{candidate_id}",
        status_code=302,
    )


@router.post("/candidates/{candidate_id}/delete")
async def delete_candidate(
    request: Request,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    service = CandidateService(db)
    candidate = await service.get_candidate(candidate_id)

    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=302)

    try:
        await db.delete(candidate)
        await db.flush()
        logger.info(
            "Candidate deleted: id=%s, email=%s, by user=%s",
            candidate_id,
            candidate.email,
            user.id,
        )
    except Exception as e:
        logger.error("Failed to delete candidate %s: %s", candidate_id, e)

    return RedirectResponse(url="/candidates", status_code=302)


@router.get("/candidates/new")
async def new_candidate_redirect(
    request: Request,
    user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    return RedirectResponse(url="/candidates/create", status_code=302)