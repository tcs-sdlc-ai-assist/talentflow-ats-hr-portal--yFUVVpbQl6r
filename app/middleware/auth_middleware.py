import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_session_cookie
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Decode session cookie and return the authenticated User, or None if not authenticated."""
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None

    payload = decode_session_cookie(session_cookie)
    if payload is None:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("Session cookie references non-existent user_id=%s", user_id)

    return user


async def require_auth(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """Dependency that raises 401 if the user is not authenticated."""
    if current_user is None:
        logger.info(
            "Unauthorized access attempt: path=%s method=%s ip=%s",
            request.url.path,
            request.method,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )
    return current_user


def require_roles(allowed_roles: list[str]):
    """Factory that returns a dependency checking the user's role against the allowed list.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles(["Admin", "Super Admin"]))])
        async def admin_page(...): ...

    Or as a parameter dependency:
        async def some_route(user: User = Depends(require_roles(["Admin"]))):
            ...
    """

    async def _role_checker(
        request: Request,
        current_user: User = Depends(require_auth),
    ) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "RBAC violation: user_id=%s username=%s role=%s attempted access to %s %s (allowed_roles=%s)",
                current_user.id,
                current_user.username,
                current_user.role,
                request.method,
                request.url.path,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}. Your role: {current_user.role}.",
            )
        return current_user

    return _role_checker


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as get_current_user but explicitly named for template contexts
    where a user may or may not be logged in."""
    return await get_current_user(request, db)