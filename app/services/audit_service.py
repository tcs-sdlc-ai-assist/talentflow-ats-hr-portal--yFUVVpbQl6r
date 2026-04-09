import json
import logging
import math
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditTrailService:
    """Service for recording and querying immutable audit log entries.

    Audit logs are append-only — no update or delete operations are provided.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: Optional[dict | str] = None,
    ) -> AuditLog:
        """Record a new immutable audit log entry.

        Args:
            actor_id: ID of the user who performed the action.
            action: Description of the action (e.g. 'Job Published', 'Candidate Rejected').
            entity_type: Type of entity affected (e.g. 'Job', 'Candidate', 'Application').
            entity_id: ID of the affected entity.
            details: Optional additional details (dict or string).

        Returns:
            The created AuditLog instance.
        """
        details_str: Optional[str] = None
        if details is not None:
            if isinstance(details, dict):
                try:
                    details_str = json.dumps(details)
                except (TypeError, ValueError) as e:
                    logger.warning("Failed to serialize audit log details: %s", e)
                    details_str = str(details)
            else:
                details_str = str(details)

        audit_log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_str,
            actor_id=actor_id,
        )

        try:
            self.db.add(audit_log)
            await self.db.flush()
            logger.info(
                "Audit log recorded: action=%s entity_type=%s entity_id=%s actor_id=%s",
                action,
                entity_type,
                entity_id,
                actor_id,
            )
            return audit_log
        except Exception as e:
            logger.error("Failed to write audit log entry: %s", e)
            raise

    async def query_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[AuditLog], int]:
        """Query audit logs with optional filtering and pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            action: Filter by action type.
            entity_type: Filter by entity type.
            entity_id: Filter by entity ID.
            actor_id: Filter by actor (user) ID.
            start_date: Filter logs from this date (inclusive).
            end_date: Filter logs until this date (inclusive).

        Returns:
            Tuple of (list of AuditLog entries, total count).
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1
        elif page_size > 100:
            page_size = 100

        base_query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if action is not None:
            base_query = base_query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)

        if entity_type is not None:
            base_query = base_query.where(AuditLog.entity_type == entity_type)
            count_query = count_query.where(AuditLog.entity_type == entity_type)

        if entity_id is not None:
            base_query = base_query.where(AuditLog.entity_id == entity_id)
            count_query = count_query.where(AuditLog.entity_id == entity_id)

        if actor_id is not None:
            base_query = base_query.where(AuditLog.actor_id == actor_id)
            count_query = count_query.where(AuditLog.actor_id == actor_id)

        if start_date is not None:
            base_query = base_query.where(AuditLog.created_at >= start_date)
            count_query = count_query.where(AuditLog.created_at >= start_date)

        if end_date is not None:
            base_query = base_query.where(AuditLog.created_at <= end_date)
            count_query = count_query.where(AuditLog.created_at <= end_date)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        items_query = (
            base_query
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(items_query)
        items = list(result.scalars().all())

        return items, total

    async def get_log_by_id(self, log_id: str) -> Optional[AuditLog]:
        """Retrieve a single audit log entry by ID.

        Args:
            log_id: The audit log entry ID.

        Returns:
            The AuditLog instance or None if not found.
        """
        result = await self.db.execute(
            select(AuditLog).where(AuditLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def get_recent_logs(self, limit: int = 10) -> list[AuditLog]:
        """Retrieve the most recent audit log entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of AuditLog entries ordered by most recent first.
        """
        if limit < 1:
            limit = 1
        elif limit > 100:
            limit = 100

        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def compute_total_pages(total: int, page_size: int) -> int:
        """Compute total number of pages for pagination.

        Args:
            total: Total number of records.
            page_size: Number of items per page.

        Returns:
            Total number of pages.
        """
        if page_size <= 0:
            return 0
        return math.ceil(total / page_size) if total > 0 else 0

    @staticmethod
    def parse_details(details_str: Optional[str]) -> Optional[dict]:
        """Parse a JSON details string back into a dict.

        Args:
            details_str: JSON string or None.

        Returns:
            Parsed dict or None.
        """
        if details_str is None:
            return None
        try:
            parsed = json.loads(details_str)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"raw": details_str}