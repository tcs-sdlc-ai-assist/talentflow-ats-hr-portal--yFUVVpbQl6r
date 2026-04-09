import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_session_cookie
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, username: str, password: str) -> Optional[tuple[User, str]]:
        """Authenticate user and return (user, session_cookie) or None on failure."""
        user = await self._get_user_by_username(username)
        if user is None:
            logger.info("Login failed: user '%s' not found", username)
            return None

        if not verify_password(password, user.hashed_password):
            logger.info("Login failed: invalid password for user '%s'", username)
            return None

        session_cookie = create_session_cookie(user.id)
        logger.info("User '%s' logged in successfully", username)
        return user, session_cookie

    async def register(
        self,
        username: str,
        password: str,
        full_name: str = "",
        role: str = "Interviewer",
    ) -> Optional[User]:
        """Register a new user. Returns the created User or None if username exists."""
        existing = await self._get_user_by_username(username)
        if existing is not None:
            logger.warning("Registration failed: username '%s' already exists", username)
            return None

        allowed_roles = {
            "Super Admin",
            "Admin",
            "Hiring Manager",
            "Recruiter",
            "Interviewer",
            "Viewer",
        }
        if role not in allowed_roles:
            logger.warning(
                "Registration failed: invalid role '%s'. Allowed: %s",
                role,
                ", ".join(sorted(allowed_roles)),
            )
            return None

        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info("User '%s' registered with role '%s'", username, role)
        return user

    async def logout(self) -> None:
        """Logout is handled at the route level by clearing the cookie.
        This method exists for any future server-side session cleanup."""
        logger.info("Logout requested")

    async def seed_default_admin(self) -> None:
        """Create the default admin user on startup if it does not already exist."""
        admin_username = settings.DEFAULT_ADMIN_USERNAME
        admin_password = settings.DEFAULT_ADMIN_PASSWORD

        existing = await self._get_user_by_username(admin_username)
        if existing is not None:
            logger.debug("Default admin user '%s' already exists, skipping seed", admin_username)
            return

        hashed_password = get_password_hash(admin_password)
        admin_user = User(
            username=admin_username,
            hashed_password=hashed_password,
            full_name="System Administrator",
            role="Admin",
        )
        self.db.add(admin_user)
        await self.db.flush()
        logger.info("Default admin user '%s' seeded successfully", admin_username)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve a user by their ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalars().first()

    async def _get_user_by_username(self, username: str) -> Optional[User]:
        """Retrieve a user by their username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalars().first()