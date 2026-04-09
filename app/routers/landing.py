import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_optional_user
from app.models.user import User
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/")
async def landing_page(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render the public landing page with hero section, CTAs, and published job listings."""
    job_service = JobService(db)

    try:
        result = await job_service.list_published_jobs(page=1, page_size=12)
        jobs = result.get("items", [])
    except Exception as e:
        logger.error("Error fetching published jobs for landing page: %s", e)
        jobs = []

    from datetime import datetime

    return templates.TemplateResponse(
        request,
        "landing.html",
        context={
            "user": user,
            "jobs": jobs,
            "current_year": datetime.now().year,
        },
    )