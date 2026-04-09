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
from app.schemas.job import JobCreate, JobFilterParams, JobStatus, JobType, ExperienceLevel, JobUpdate
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/jobs")
async def list_jobs(
    request: Request,
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    experience_level: Optional[str] = Query(None),
    is_remote: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    filter_status = None
    if status:
        try:
            filter_status = JobStatus(status)
        except ValueError:
            filter_status = None

    filter_job_type = None
    if job_type:
        try:
            filter_job_type = JobType(job_type)
        except ValueError:
            filter_job_type = None

    filter_experience_level = None
    if experience_level:
        try:
            filter_experience_level = ExperienceLevel(experience_level)
        except ValueError:
            filter_experience_level = None

    filters = JobFilterParams(
        status=filter_status,
        department=department,
        job_type=filter_job_type,
        experience_level=filter_experience_level,
        is_remote=is_remote,
        search=search,
        page=page,
        page_size=page_size,
    )

    result = await job_service.list_jobs(filters=filters)
    departments = await job_service.get_departments()

    context = {
        "user": current_user,
        "jobs": result["items"],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
        "departments": departments,
        "filters": {
            "status": status or "",
            "department": department or "",
            "search": search or "",
            "job_type": job_type or "",
            "experience_level": experience_level or "",
            "is_remote": is_remote,
        },
    }

    return templates.TemplateResponse(request, "jobs/list.html", context=context)


@router.get("/jobs/create")
async def create_job_form(
    request: Request,
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Hiring Manager", "Recruiter"])
    ),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)
    hiring_managers = await job_service.list_hiring_managers()

    context = {
        "user": current_user,
        "job": None,
        "hiring_managers": hiring_managers,
    }

    return templates.TemplateResponse(request, "jobs/form.html", context=context)


@router.post("/jobs/create")
async def create_job(
    request: Request,
    title: str = Form(...),
    department: str = Form(""),
    location: str = Form(""),
    job_type: str = Form(""),
    experience_level: str = Form(""),
    is_remote: str = Form(""),
    openings: int = Form(1),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    salary_currency: str = Form("USD"),
    description: str = Form(""),
    requirements: str = Form(""),
    responsibilities: str = Form(""),
    benefits: str = Form(""),
    status: str = Form("Draft"),
    hiring_manager_id: str = Form(""),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Hiring Manager", "Recruiter"])
    ),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    parsed_salary_min = None
    if salary_min and salary_min.strip():
        try:
            parsed_salary_min = float(salary_min)
        except (ValueError, TypeError):
            parsed_salary_min = None

    parsed_salary_max = None
    if salary_max and salary_max.strip():
        try:
            parsed_salary_max = float(salary_max)
        except (ValueError, TypeError):
            parsed_salary_max = None

    parsed_job_type = None
    if job_type and job_type.strip():
        try:
            parsed_job_type = JobType(job_type)
        except ValueError:
            parsed_job_type = None

    parsed_experience_level = None
    if experience_level and experience_level.strip():
        try:
            parsed_experience_level = ExperienceLevel(experience_level)
        except ValueError:
            parsed_experience_level = None

    parsed_status = JobStatus.DRAFT
    if status and status.strip():
        try:
            parsed_status = JobStatus(status)
        except ValueError:
            parsed_status = JobStatus.DRAFT

    remote = is_remote.lower() in ("true", "on", "1", "yes") if is_remote else False

    try:
        job_data = JobCreate(
            title=title,
            description=description if description.strip() else None,
            department=department if department.strip() else None,
            location=location if location.strip() else None,
            job_type=parsed_job_type,
            experience_level=parsed_experience_level,
            salary_min=parsed_salary_min,
            salary_max=parsed_salary_max,
            salary_currency=salary_currency if salary_currency.strip() else "USD",
            requirements=requirements if requirements.strip() else None,
            responsibilities=responsibilities if responsibilities.strip() else None,
            benefits=benefits if benefits.strip() else None,
            is_remote=remote,
            openings=openings,
            status=parsed_status,
        )

        user_id = hiring_manager_id.strip() if hiring_manager_id and hiring_manager_id.strip() else current_user.id

        job = await job_service.create_job(job_data, user_id=user_id)

        logger.info(
            "Job created: id=%s title=%s by user=%s",
            job.id,
            job.title,
            current_user.id,
        )

        return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)

    except (ValueError, Exception) as e:
        logger.error("Error creating job: %s", e)
        hiring_managers = await job_service.list_hiring_managers()
        context = {
            "user": current_user,
            "job": None,
            "hiring_managers": hiring_managers,
            "error": str(e),
        }
        return templates.TemplateResponse(
            request, "jobs/form.html", context=context, status_code=400
        )


@router.get("/jobs/{job_id}")
async def job_detail(
    request: Request,
    job_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if job is None:
        context = {
            "user": current_user,
            "error": "Job not found.",
        }
        return templates.TemplateResponse(
            request, "jobs/list.html", context={
                "user": current_user,
                "jobs": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "total_pages": 0,
                "departments": [],
                "filters": {},
                "error": "Job not found.",
            },
            status_code=404,
        )

    from app.services.application_service import ApplicationService

    app_service = ApplicationService(db)
    applications_list = await app_service.get_applications_for_job(job_id)

    application_items = []
    for app in applications_list:
        candidate_name = None
        if app.candidate:
            candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
        application_items.append({
            "id": app.id,
            "job_id": app.job_id,
            "candidate_id": app.candidate_id,
            "candidate_name": candidate_name,
            "status": app.status,
            "source": app.source,
            "applied_at": app.applied_at,
            "updated_at": app.updated_at,
        })

    hiring_manager = None
    if job.created_by:
        from app.services.auth_service import AuthService

        auth_service = AuthService(db)
        hiring_manager = await auth_service.get_user_by_id(job.created_by)

    context = {
        "user": current_user,
        "job": job,
        "applications": application_items,
        "hiring_manager": hiring_manager,
    }

    return templates.TemplateResponse(request, "jobs/detail.html", context=context)


@router.get("/jobs/{job_id}/edit")
async def edit_job_form(
    request: Request,
    job_id: str,
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Hiring Manager", "Recruiter"])
    ),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if job is None:
        return RedirectResponse(url="/jobs", status_code=303)

    hiring_managers = await job_service.list_hiring_managers()

    context = {
        "user": current_user,
        "job": job,
        "hiring_managers": hiring_managers,
    }

    return templates.TemplateResponse(request, "jobs/form.html", context=context)


@router.post("/jobs/{job_id}/edit")
async def update_job(
    request: Request,
    job_id: str,
    title: str = Form(...),
    department: str = Form(""),
    location: str = Form(""),
    job_type: str = Form(""),
    experience_level: str = Form(""),
    is_remote: str = Form(""),
    openings: int = Form(1),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    salary_currency: str = Form("USD"),
    description: str = Form(""),
    requirements: str = Form(""),
    responsibilities: str = Form(""),
    benefits: str = Form(""),
    status: str = Form(""),
    hiring_manager_id: str = Form(""),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Hiring Manager", "Recruiter"])
    ),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if job is None:
        return RedirectResponse(url="/jobs", status_code=303)

    parsed_salary_min = None
    if salary_min and salary_min.strip():
        try:
            parsed_salary_min = float(salary_min)
        except (ValueError, TypeError):
            parsed_salary_min = None

    parsed_salary_max = None
    if salary_max and salary_max.strip():
        try:
            parsed_salary_max = float(salary_max)
        except (ValueError, TypeError):
            parsed_salary_max = None

    parsed_job_type = None
    if job_type and job_type.strip():
        try:
            parsed_job_type = JobType(job_type)
        except ValueError:
            parsed_job_type = None

    parsed_experience_level = None
    if experience_level and experience_level.strip():
        try:
            parsed_experience_level = ExperienceLevel(experience_level)
        except ValueError:
            parsed_experience_level = None

    remote = is_remote.lower() in ("true", "on", "1", "yes") if is_remote else False

    try:
        update_data = JobUpdate(
            title=title,
            description=description if description.strip() else None,
            department=department if department.strip() else None,
            location=location if location.strip() else None,
            job_type=parsed_job_type,
            experience_level=parsed_experience_level,
            salary_min=parsed_salary_min,
            salary_max=parsed_salary_max,
            salary_currency=salary_currency if salary_currency.strip() else None,
            requirements=requirements if requirements.strip() else None,
            responsibilities=responsibilities if responsibilities.strip() else None,
            benefits=benefits if benefits.strip() else None,
            is_remote=remote,
            openings=openings,
        )

        updated_job = await job_service.update_job(job_id, update_data)

        if updated_job is None:
            return RedirectResponse(url="/jobs", status_code=303)

        if status and status.strip() and status.strip() != updated_job.status:
            try:
                await job_service.update_status(job_id, status.strip())
            except ValueError as ve:
                logger.warning("Status transition failed during edit: %s", ve)

        if hiring_manager_id and hiring_manager_id.strip():
            try:
                await job_service.assign_hiring_manager(job_id, hiring_manager_id.strip())
            except ValueError as ve:
                logger.warning("Hiring manager assignment failed: %s", ve)

        logger.info(
            "Job updated: id=%s by user=%s",
            job_id,
            current_user.id,
        )

        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    except (ValueError, Exception) as e:
        logger.error("Error updating job %s: %s", job_id, e)
        hiring_managers = await job_service.list_hiring_managers()
        context = {
            "user": current_user,
            "job": job,
            "hiring_managers": hiring_managers,
            "error": str(e),
        }
        return templates.TemplateResponse(
            request, "jobs/form.html", context=context, status_code=400
        )


@router.post("/jobs/{job_id}/status")
async def update_job_status(
    request: Request,
    job_id: str,
    status: str = Form(...),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Hiring Manager", "Recruiter"])
    ),
    db: AsyncSession = Depends(get_db),
):
    job_service = JobService(db)

    try:
        job = await job_service.update_status(job_id, status.strip())

        if job is None:
            return RedirectResponse(url="/jobs", status_code=303)

        logger.info(
            "Job status updated: id=%s status=%s by user=%s",
            job_id,
            status,
            current_user.id,
        )

        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    except ValueError as e:
        logger.warning("Job status update failed for %s: %s", job_id, e)
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
    except Exception as e:
        logger.error("Error updating job status %s: %s", job_id, e)
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)