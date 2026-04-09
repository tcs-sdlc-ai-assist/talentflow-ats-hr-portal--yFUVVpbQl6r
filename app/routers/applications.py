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
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
from app.schemas.application import (
    ALLOWED_TRANSITIONS,
    VALID_STATUSES,
    ApplicationStatusUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/applications")
async def list_applications(
    request: Request,
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    app_service = ApplicationService(db)
    job_service = JobService(db)

    result = await app_service.list_applications(
        status=status,
        job_id=job_id,
        page=page,
        page_size=page_size,
    )

    jobs_data = await job_service.list_jobs()
    jobs = jobs_data.get("items", [])

    filters = {
        "status": status or "",
        "job_id": job_id or "",
    }

    return templates.TemplateResponse(
        request,
        "applications/list.html",
        context={
            "user": current_user,
            "applications": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.size,
            "total_pages": result.pages,
            "statuses": VALID_STATUSES,
            "jobs": jobs,
            "filters": filters,
        },
    )


@router.get("/applications/pipeline")
async def pipeline_view(
    request: Request,
    job_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    app_service = ApplicationService(db)
    job_service = JobService(db)

    pipeline = await app_service.kanban_view(job_id=job_id)

    jobs_data = await job_service.list_jobs()
    job_filter_options = jobs_data.get("items", [])

    selected_job = None
    if job_id:
        selected_job = await job_service.get_job(job_id)

    return templates.TemplateResponse(
        request,
        "applications/pipeline.html",
        context={
            "user": current_user,
            "pipeline": pipeline,
            "job_filter_options": job_filter_options,
            "selected_job_id": job_id or "",
            "job": selected_job,
        },
    )


@router.get("/applications/new")
async def new_application_form(
    request: Request,
    job_id: Optional[str] = Query(None),
    candidate_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    job_service = JobService(db)
    candidate_service = CandidateService(db)

    jobs_data = await job_service.list_jobs()
    jobs = jobs_data.get("items", [])

    candidates_data = await candidate_service.list_candidates(page=1, page_size=1000)
    candidates = candidates_data.get("items", [])

    return templates.TemplateResponse(
        request,
        "applications/form.html",
        context={
            "user": current_user,
            "jobs": jobs,
            "candidates": candidates,
            "selected_job_id": job_id or "",
            "selected_candidate_id": candidate_id or "",
            "error": None,
        },
    )


@router.post("/applications/new")
async def create_application(
    request: Request,
    job_id: str = Form(...),
    candidate_id: str = Form(...),
    cover_letter: str = Form(""),
    resume_url: str = Form(""),
    source: str = Form("Direct"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    from app.schemas.application import ApplicationCreate

    app_service = ApplicationService(db)

    try:
        data = ApplicationCreate(
            job_id=job_id,
            candidate_id=candidate_id,
            cover_letter=cover_letter if cover_letter.strip() else None,
            resume_url=resume_url if resume_url.strip() else None,
            source=source if source.strip() else "Direct",
        )
        application = await app_service.create_application(data, actor_id=current_user.id)
        logger.info(
            "Application created by user %s: application_id=%s",
            current_user.id,
            application.id,
        )
        return RedirectResponse(
            url=f"/applications/{application.id}",
            status_code=302,
        )
    except ValueError as e:
        logger.warning("Application creation failed: %s", e)

        job_service = JobService(db)
        candidate_service = CandidateService(db)

        jobs_data = await job_service.list_jobs()
        jobs = jobs_data.get("items", [])

        candidates_data = await candidate_service.list_candidates(page=1, page_size=1000)
        candidates = candidates_data.get("items", [])

        return templates.TemplateResponse(
            request,
            "applications/form.html",
            context={
                "user": current_user,
                "jobs": jobs,
                "candidates": candidates,
                "selected_job_id": job_id,
                "selected_candidate_id": candidate_id,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/applications/{application_id}")
async def application_detail(
    request: Request,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=302)

    app_service = ApplicationService(db)
    application = await app_service.get_application(application_id)

    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": current_user,
                "application": None,
                "candidate": None,
                "job": None,
                "interviews": [],
                "allowed_transitions": [],
                "error": f"Application with id '{application_id}' not found.",
            },
            status_code=404,
        )

    candidate = application.candidate
    job = application.job
    interviews = list(application.interviews) if application.interviews else []

    allowed_transitions = ALLOWED_TRANSITIONS.get(application.status, [])

    return templates.TemplateResponse(
        request,
        "applications/detail.html",
        context={
            "user": current_user,
            "application": application,
            "candidate": candidate,
            "job": job,
            "interviews": interviews,
            "allowed_transitions": allowed_transitions,
        },
    )


@router.post("/applications/{application_id}/status")
async def update_application_status(
    request: Request,
    application_id: str,
    status: str = Form(...),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    app_service = ApplicationService(db)

    try:
        status_update = ApplicationStatusUpdate(
            status=status,
            notes=notes if notes.strip() else None,
        )
        application = await app_service.update_status(
            application_id=application_id,
            status_update=status_update,
            actor_id=current_user.id,
        )
        logger.info(
            "Application %s status updated to '%s' by user %s",
            application_id,
            status,
            current_user.id,
        )
        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=302,
        )
    except ValueError as e:
        logger.warning(
            "Application status update failed for %s: %s",
            application_id,
            e,
        )
        application = await app_service.get_application(application_id)

        if application is None:
            return RedirectResponse(url="/applications", status_code=302)

        candidate = application.candidate
        job = application.job
        interviews = list(application.interviews) if application.interviews else []
        allowed_transitions = ALLOWED_TRANSITIONS.get(application.status, [])

        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": current_user,
                "application": application,
                "candidate": candidate,
                "job": job,
                "interviews": interviews,
                "allowed_transitions": allowed_transitions,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/applications/{application_id}/edit")
async def edit_application_form(
    request: Request,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])),
):
    app_service = ApplicationService(db)
    application = await app_service.get_application(application_id)

    if application is None:
        return RedirectResponse(url="/applications", status_code=302)

    return templates.TemplateResponse(
        request,
        "applications/detail.html",
        context={
            "user": current_user,
            "application": application,
            "candidate": application.candidate,
            "job": application.job,
            "interviews": list(application.interviews) if application.interviews else [],
            "allowed_transitions": ALLOWED_TRANSITIONS.get(application.status, []),
        },
    )