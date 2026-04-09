import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import require_auth, require_roles
from app.models.user import User
from app.services.audit_service import AuditTrailService
from app.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Render the role-specific dashboard with metrics and contextual information."""
    try:
        dashboard_service = DashboardService(db)
        context = await dashboard_service.get_dashboard_context(current_user)

        template_context = {
            "user": current_user,
        }

        if "stats" in context:
            template_context["stats"] = context["stats"]
        if "pipeline_stats" in context:
            template_context["pipeline_stats"] = context["pipeline_stats"]
        if "recent_audit_logs" in context:
            template_context["recent_audit_logs"] = context["recent_audit_logs"]
        if "upcoming_interviews" in context:
            template_context["upcoming_interviews"] = context["upcoming_interviews"]
        if "my_jobs" in context:
            template_context["my_jobs"] = context["my_jobs"]
        if "pending_feedback" in context:
            template_context["pending_feedback"] = context["pending_feedback"]
        if "error" in context:
            template_context["error"] = context["error"]

        return templates.TemplateResponse(
            request,
            "dashboard/index.html",
            context=template_context,
        )

    except Exception as e:
        logger.error(
            "Error rendering dashboard for user %s (role=%s): %s",
            current_user.id,
            current_user.role,
            e,
        )
        return templates.TemplateResponse(
            request,
            "dashboard/index.html",
            context={
                "user": current_user,
                "error": "Unable to load dashboard data. Please try again.",
            },
        )


@router.get("/dashboard/audit-logs")
async def audit_logs_page(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    action: Optional[str] = Query(default=None, description="Filter by action type"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(default=None, description="Filter by entity ID"),
    actor_id: Optional[str] = Query(default=None, description="Filter by actor ID"),
    start_date: Optional[str] = Query(default=None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Filter until date (YYYY-MM-DD)"),
    current_user: User = Depends(require_roles(["Admin", "Super Admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Render the audit log view with filtering and pagination. Admin/Super Admin only."""
    try:
        audit_service = AuditTrailService(db)

        parsed_start_date: Optional[datetime] = None
        parsed_end_date: Optional[datetime] = None

        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                logger.warning("Invalid start_date format: %s", start_date)
                parsed_start_date = None

        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
            except ValueError:
                logger.warning("Invalid end_date format: %s", end_date)
                parsed_end_date = None

        logs, total = await audit_service.query_logs(
            page=page,
            page_size=page_size,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )

        total_pages = audit_service.compute_total_pages(total, page_size)

        parsed_logs = []
        for log in logs:
            parsed_details = audit_service.parse_details(log.details)
            parsed_logs.append({
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": parsed_details,
                "details_raw": log.details,
                "actor_id": log.actor_id,
                "actor": log.actor,
                "created_at": log.created_at,
            })

        filters = {
            "action": action or "",
            "entity_type": entity_type or "",
            "entity_id": entity_id or "",
            "actor_id": actor_id or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
        }

        return templates.TemplateResponse(
            request,
            "dashboard/audit_logs.html",
            context={
                "user": current_user,
                "logs": parsed_logs,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "filters": filters,
            },
        )

    except Exception as e:
        logger.error(
            "Error rendering audit logs for user %s: %s",
            current_user.id,
            e,
        )
        return templates.TemplateResponse(
            request,
            "dashboard/audit_logs.html",
            context={
                "user": current_user,
                "logs": [],
                "total": 0,
                "page": 1,
                "page_size": page_size,
                "total_pages": 0,
                "filters": {
                    "action": "",
                    "entity_type": "",
                    "entity_id": "",
                    "actor_id": "",
                    "start_date": "",
                    "end_date": "",
                },
                "error": "Unable to load audit logs. Please try again.",
            },
        )


@router.get("/api/dashboard/metrics")
async def dashboard_metrics_api(
    request: Request,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return dashboard metrics as JSON for the authenticated user."""
    try:
        dashboard_service = DashboardService(db)
        metrics = await dashboard_service.get_metrics(current_user)

        return {
            "role": current_user.role,
            "metrics": metrics,
        }

    except Exception as e:
        logger.error(
            "Error fetching dashboard metrics for user %s: %s",
            current_user.id,
            e,
        )
        return {
            "role": current_user.role,
            "metrics": {
                "total_jobs": 0,
                "open_jobs": 0,
                "total_candidates": 0,
                "total_applications": 0,
                "total_interviews": 0,
                "scheduled_interviews": 0,
                "completed_interviews": 0,
            },
        }


@router.get("/api/audit-logs")
async def audit_logs_api(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    current_user: User = Depends(require_roles(["Admin", "Super Admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Return audit logs as JSON with filtering and pagination. Admin/Super Admin only."""
    try:
        audit_service = AuditTrailService(db)

        parsed_start_date: Optional[datetime] = None
        parsed_end_date: Optional[datetime] = None

        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                parsed_start_date = None

        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
            except ValueError:
                parsed_end_date = None

        logs, total = await audit_service.query_logs(
            page=page,
            page_size=page_size,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )

        total_pages = audit_service.compute_total_pages(total, page_size)

        items = []
        for log in logs:
            parsed_details = audit_service.parse_details(log.details)
            items.append({
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": parsed_details,
                "actor_id": log.actor_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return {
            "logs": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        }

    except Exception as e:
        logger.error("Error fetching audit logs API for user %s: %s", current_user.id, e)
        return {
            "logs": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
            },
        }