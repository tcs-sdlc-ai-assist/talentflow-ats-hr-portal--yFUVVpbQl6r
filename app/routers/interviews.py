import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_auth, require_roles
from app.models.user import User
from app.services.interview_service import InterviewService
from app.services.application_service import ApplicationService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/interviews")
async def list_interviews(
    request: Request,
    status: Optional[str] = Query(None),
    interview_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    interview_service = InterviewService(db)

    parsed_from_date: Optional[datetime] = None
    parsed_to_date: Optional[datetime] = None

    if from_date:
        try:
            parsed_from_date = datetime.strptime(from_date, "%Y-%m-%d")
        except ValueError:
            parsed_from_date = None

    if to_date:
        try:
            parsed_to_date = datetime.strptime(to_date, "%Y-%m-%d")
        except ValueError:
            parsed_to_date = None

    result = await interview_service.list_interviews(
        page=page,
        page_size=page_size,
        status=status,
        interview_type=interview_type,
        from_date=parsed_from_date,
        to_date=parsed_to_date,
    )

    stats = await interview_service.get_interview_stats()

    filters = {
        "status": status or "",
        "interview_type": interview_type or "",
        "from_date": from_date or "",
        "to_date": to_date or "",
    }

    return templates.TemplateResponse(
        request,
        "interviews/list.html",
        context={
            "user": current_user,
            "interviews": result["items"],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
            "total_pages": result["total_pages"],
            "filters": filters,
            "stats": stats,
        },
    )


@router.get("/interviews/my")
async def my_interviews(
    request: Request,
    filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    interview_service = InterviewService(db)

    result = await interview_service.list_my_interviews(
        interviewer_id=current_user.id,
        page=page,
        page_size=page_size,
        filter_type=filter if filter and filter != "all" else None,
    )

    return templates.TemplateResponse(
        request,
        "interviews/my.html",
        context={
            "user": current_user,
            "interviews": result["items"],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
            "total_pages": result["total_pages"],
            "pending_feedback_count": result.get("pending_feedback_count", 0),
            "filter": filter or "all",
        },
    )


@router.get("/interviews/schedule")
async def schedule_interview_form(
    request: Request,
    application_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])
    ),
):
    from sqlalchemy import select
    from app.models.application import Application
    from app.models.user import User as UserModel

    application = None
    if application_id:
        app_service = ApplicationService(db)
        application = await app_service.get_application(application_id)

    result = await db.execute(
        select(UserModel).where(
            UserModel.role.in_(["Admin", "Super Admin", "Interviewer", "Hiring Manager", "Recruiter"])
        ).order_by(UserModel.username)
    )
    interviewers = list(result.scalars().all())

    app_service = ApplicationService(db)
    applications_result = await app_service.list_applications(page=1, page_size=200)
    applications = applications_result.items

    return templates.TemplateResponse(
        request,
        "interviews/schedule_form.html",
        context={
            "user": current_user,
            "application": application,
            "application_id": application_id or "",
            "interviewers": interviewers,
            "applications": applications,
        },
    )


@router.post("/interviews/schedule")
async def schedule_interview_submit(
    request: Request,
    application_id: str = Form(...),
    interviewer_id: str = Form(...),
    scheduled_at: str = Form(...),
    interview_type: str = Form(...),
    duration_minutes: int = Form(60),
    location: str = Form(""),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])
    ),
):
    interview_service = InterviewService(db)

    try:
        parsed_scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
    except ValueError:
        try:
            parsed_scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M")
        except ValueError:
            from sqlalchemy import select
            from app.models.user import User as UserModel

            result = await db.execute(
                select(UserModel).where(
                    UserModel.role.in_(["Admin", "Super Admin", "Interviewer", "Hiring Manager", "Recruiter"])
                ).order_by(UserModel.username)
            )
            interviewers = list(result.scalars().all())

            app_service = ApplicationService(db)
            applications_result = await app_service.list_applications(page=1, page_size=200)

            return templates.TemplateResponse(
                request,
                "interviews/schedule_form.html",
                context={
                    "user": current_user,
                    "application": None,
                    "application_id": application_id,
                    "interviewers": interviewers,
                    "applications": applications_result.items,
                    "error": "Invalid date/time format. Please use the date picker.",
                },
                status_code=400,
            )

    try:
        interview = await interview_service.schedule_interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=parsed_scheduled_at,
            interview_type=interview_type,
            duration_minutes=duration_minutes,
            location=location.strip() if location else None,
            notes=notes.strip() if notes else None,
        )

        logger.info(
            "Interview scheduled: id=%s by user=%s",
            interview.id,
            current_user.id,
        )

        return RedirectResponse(
            url=f"/interviews/{interview.id}",
            status_code=303,
        )

    except ValueError as e:
        from sqlalchemy import select
        from app.models.user import User as UserModel

        result = await db.execute(
            select(UserModel).where(
                UserModel.role.in_(["Admin", "Super Admin", "Interviewer", "Hiring Manager", "Recruiter"])
            ).order_by(UserModel.username)
        )
        interviewers = list(result.scalars().all())

        app_service = ApplicationService(db)
        applications_result = await app_service.list_applications(page=1, page_size=200)

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": current_user,
                "application": None,
                "application_id": application_id,
                "interviewers": interviewers,
                "applications": applications_result.items,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/interviews/{interview_id}")
async def interview_detail(
    request: Request,
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    interview_service = InterviewService(db)
    interview = await interview_service.get_interview(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/list.html",
            context={
                "user": current_user,
                "interviews": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "total_pages": 1,
                "filters": {},
                "stats": {},
                "flash_messages": [{"type": "error", "text": "Interview not found."}],
            },
            status_code=404,
        )

    interview_dict = interview_service._interview_to_dict(interview)

    application = interview.application if interview.application else None
    candidate = application.candidate if application and application.candidate else None
    job = application.job if application and application.job else None
    feedback = interview.feedback if interview.feedback else None

    return templates.TemplateResponse(
        request,
        "interviews/detail.html",
        context={
            "user": current_user,
            "interview": interview,
            "interview_data": interview_dict,
            "application": application,
            "candidate": candidate,
            "job": job,
            "feedback": feedback,
        },
    )


@router.get("/interviews/{interview_id}/edit")
async def edit_interview_form(
    request: Request,
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])
    ),
):
    interview_service = InterviewService(db)
    interview = await interview_service.get_interview(interview_id)

    if interview is None:
        return RedirectResponse(url="/interviews", status_code=303)

    from sqlalchemy import select
    from app.models.user import User as UserModel

    result = await db.execute(
        select(UserModel).where(
            UserModel.role.in_(["Admin", "Super Admin", "Interviewer", "Hiring Manager", "Recruiter"])
        ).order_by(UserModel.username)
    )
    interviewers = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "interviews/edit_form.html",
        context={
            "user": current_user,
            "interview": interview,
            "interviewers": interviewers,
        },
    )


@router.post("/interviews/{interview_id}/edit")
async def edit_interview_submit(
    request: Request,
    interview_id: str,
    scheduled_at: str = Form(""),
    interview_type: str = Form(""),
    duration_minutes: int = Form(60),
    location: str = Form(""),
    notes: str = Form(""),
    status: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])
    ),
):
    interview_service = InterviewService(db)

    parsed_scheduled_at: Optional[datetime] = None
    if scheduled_at:
        try:
            parsed_scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
        except ValueError:
            try:
                parsed_scheduled_at = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M")
            except ValueError:
                parsed_scheduled_at = None

    try:
        interview = await interview_service.update_interview(
            interview_id=interview_id,
            scheduled_at=parsed_scheduled_at,
            interview_type=interview_type if interview_type else None,
            duration_minutes=duration_minutes,
            location=location.strip() if location.strip() else None,
            notes=notes.strip() if notes.strip() else None,
            status=status if status else None,
        )

        logger.info(
            "Interview updated: id=%s by user=%s",
            interview.id,
            current_user.id,
        )

        return RedirectResponse(
            url=f"/interviews/{interview_id}",
            status_code=303,
        )

    except ValueError as e:
        interview = await interview_service.get_interview(interview_id)

        from sqlalchemy import select
        from app.models.user import User as UserModel

        result = await db.execute(
            select(UserModel).where(
                UserModel.role.in_(["Admin", "Super Admin", "Interviewer", "Hiring Manager", "Recruiter"])
            ).order_by(UserModel.username)
        )
        interviewers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "interviews/edit_form.html",
            context={
                "user": current_user,
                "interview": interview,
                "interviewers": interviewers,
                "error": str(e),
            },
            status_code=400,
        )


@router.post("/interviews/{interview_id}/cancel")
async def cancel_interview(
    request: Request,
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])
    ),
):
    interview_service = InterviewService(db)

    try:
        await interview_service.cancel_interview(interview_id)
        logger.info(
            "Interview cancelled: id=%s by user=%s",
            interview_id,
            current_user.id,
        )
    except ValueError as e:
        logger.warning(
            "Failed to cancel interview id=%s: %s",
            interview_id,
            str(e),
        )

    return RedirectResponse(
        url=f"/interviews/{interview_id}",
        status_code=303,
    )


@router.get("/interviews/{interview_id}/feedback")
async def feedback_form(
    request: Request,
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    interview_service = InterviewService(db)
    interview = await interview_service.get_interview(interview_id)

    if interview is None:
        return RedirectResponse(url="/interviews", status_code=303)

    application = interview.application if interview.application else None
    candidate = application.candidate if application and application.candidate else None
    job = application.job if application and application.job else None

    existing_feedback = await interview_service.get_feedback(interview_id)

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": current_user,
            "interview": interview,
            "application": application,
            "candidate": candidate,
            "job": job,
            "existing_feedback": existing_feedback,
            "errors": {},
        },
    )


@router.post("/interviews/{interview_id}/feedback")
async def submit_feedback(
    request: Request,
    interview_id: str,
    rating: int = Form(...),
    feedback_text: str = Form(...),
    recommendation: str = Form(""),
    strengths: str = Form(""),
    weaknesses: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    interview_service = InterviewService(db)

    errors: dict = {}

    if not 1 <= rating <= 5:
        errors["rating"] = "Rating must be between 1 and 5."

    if not feedback_text or not feedback_text.strip():
        errors["feedback_text"] = "Feedback text is required."

    recommendation_value: Optional[str] = None
    if recommendation and recommendation.strip():
        allowed_recommendations = {"strong_hire", "hire", "no_hire", "strong_no_hire"}
        if recommendation.strip() not in allowed_recommendations:
            errors["recommendation"] = f"Invalid recommendation. Must be one of: {', '.join(sorted(allowed_recommendations))}"
        else:
            recommendation_value = recommendation.strip()

    if errors:
        interview = await interview_service.get_interview(interview_id)
        if interview is None:
            return RedirectResponse(url="/interviews", status_code=303)

        application = interview.application if interview.application else None
        candidate = application.candidate if application and application.candidate else None
        job = application.job if application and application.job else None
        existing_feedback = await interview_service.get_feedback(interview_id)

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": interview,
                "application": application,
                "candidate": candidate,
                "job": job,
                "existing_feedback": existing_feedback,
                "errors": errors,
            },
            status_code=400,
        )

    try:
        feedback = await interview_service.submit_feedback(
            interview_id=interview_id,
            interviewer_id=current_user.id,
            rating=rating,
            feedback_text=feedback_text.strip(),
            recommendation=recommendation_value,
            strengths=strengths.strip() if strengths and strengths.strip() else None,
            weaknesses=weaknesses.strip() if weaknesses and weaknesses.strip() else None,
        )

        logger.info(
            "Feedback submitted: interview_id=%s by user=%s rating=%d",
            interview_id,
            current_user.id,
            rating,
        )

        return RedirectResponse(
            url=f"/interviews/{interview_id}",
            status_code=303,
        )

    except ValueError as e:
        interview = await interview_service.get_interview(interview_id)
        if interview is None:
            return RedirectResponse(url="/interviews", status_code=303)

        application = interview.application if interview.application else None
        candidate = application.candidate if application and application.candidate else None
        job = application.job if application and application.job else None
        existing_feedback = await interview_service.get_feedback(interview_id)

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": interview,
                "application": application,
                "candidate": candidate,
                "job": job,
                "existing_feedback": existing_feedback,
                "errors": {"feedback_text": str(e)},
            },
            status_code=400,
        )


@router.get("/interviews/new")
async def new_interview_redirect(
    request: Request,
    application_id: Optional[str] = Query(None),
    current_user: User = Depends(
        require_roles(["Admin", "Super Admin", "Recruiter", "Hiring Manager"])
    ),
):
    url = "/interviews/schedule"
    if application_id:
        url = f"/interviews/schedule?application_id={application_id}"
    return RedirectResponse(url=url, status_code=303)