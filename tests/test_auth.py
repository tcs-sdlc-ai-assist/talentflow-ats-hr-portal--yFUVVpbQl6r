import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import (
    create_session_cookie,
    decode_session_cookie,
    get_password_hash,
    verify_password,
)
from app.services.auth_service import AuthService


class TestRegistration:
    """Tests for user registration flow."""

    async def test_register_page_returns_200(self, client: httpx.AsyncClient):
        response = await client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    async def test_register_creates_user_with_interviewer_role(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "newuser",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.username == "newuser"
        assert user.role == "Interviewer"
        assert verify_password("securepass123", user.hashed_password)

    async def test_register_sets_session_cookie(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "cookieuser",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "session" in response.cookies

    async def test_register_duplicate_username_fails(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        hashed = get_password_hash("existingpass1")
        existing_user = User(
            username="existinguser",
            hashed_password=hashed,
            role="Interviewer",
        )
        db_session.add(existing_user)
        await db_session.flush()

        response = await client.post(
            "/auth/register",
            data={
                "username": "existinguser",
                "password": "newpassword1",
                "confirm_password": "newpassword1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already taken" in response.text

    async def test_register_password_mismatch_fails(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "mismatchuser",
                "password": "password123",
                "confirm_password": "differentpass",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "do not match" in response.text

    async def test_register_short_password_fails(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "shortpwuser",
                "password": "short",
                "confirm_password": "short",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least 8 characters" in response.text

    async def test_register_short_username_fails(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "ab",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "at least 3 characters" in response.text

    async def test_register_invalid_username_chars_fails(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "bad user!",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "alphanumeric" in response.text

    async def test_register_redirects_if_already_authenticated(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get("/auth/register", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"


class TestLogin:
    """Tests for user login flow."""

    async def test_login_page_returns_200(self, client: httpx.AsyncClient):
        response = await client.get("/auth/login")
        assert response.status_code == 200
        assert "Sign in" in response.text

    async def test_login_valid_credentials_redirects_to_dashboard(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        hashed = get_password_hash("validpass123")
        user = User(
            username="loginuser",
            hashed_password=hashed,
            role="Admin",
            full_name="Login User",
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            data={"username": "loginuser", "password": "validpass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"
        assert "session" in response.cookies

    async def test_login_invalid_password_returns_401(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        hashed = get_password_hash("correctpass1")
        user = User(
            username="wrongpwuser",
            hashed_password=hashed,
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            data={"username": "wrongpwuser", "password": "wrongpassword"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    async def test_login_nonexistent_user_returns_401(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/login",
            data={"username": "ghostuser", "password": "anypassword1"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    async def test_login_empty_username_returns_400(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/login",
            data={"username": "", "password": "somepassword"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Username is required" in response.text

    async def test_login_empty_password_returns_400(self, client: httpx.AsyncClient):
        response = await client.post(
            "/auth/login",
            data={"username": "someuser", "password": ""},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Password is required" in response.text

    async def test_login_redirects_if_already_authenticated(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get("/auth/login", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

    async def test_login_sets_httponly_cookie(
        self, client: httpx.AsyncClient, db_session: AsyncSession
    ):
        hashed = get_password_hash("cookietest1")
        user = User(
            username="cookietestuser",
            hashed_password=hashed,
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            data={"username": "cookietestuser", "password": "cookietest1"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        set_cookie_header = response.headers.get("set-cookie", "")
        assert "httponly" in set_cookie_header.lower()
        assert "session=" in set_cookie_header


class TestLogout:
    """Tests for user logout flow."""

    async def test_logout_clears_session_cookie(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/auth/login"

        set_cookie_header = response.headers.get("set-cookie", "")
        assert "session=" in set_cookie_header
        lower_header = set_cookie_header.lower()
        has_empty = 'session=""' in set_cookie_header or "session=;" in set_cookie_header
        has_max_age_zero = "max-age=0" in lower_header
        has_expires_past = "expires=" in lower_header
        assert has_empty or has_max_age_zero or has_expires_past

    async def test_logout_redirects_to_login(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/auth/login"


class TestDefaultAdminSeeding:
    """Tests for default admin user seeding on startup."""

    async def test_seed_default_admin_creates_admin_user(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        await auth_service.seed_default_admin()
        await db_session.flush()

        result = await db_session.execute(
            select(User).where(User.username == "admin")
        )
        admin = result.scalar_one_or_none()
        assert admin is not None
        assert admin.role == "Admin"
        assert admin.full_name == "System Administrator"
        assert verify_password("admin123", admin.hashed_password)

    async def test_seed_default_admin_is_idempotent(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        await auth_service.seed_default_admin()
        await db_session.flush()

        await auth_service.seed_default_admin()
        await db_session.flush()

        result = await db_session.execute(
            select(User).where(User.username == "admin")
        )
        admins = result.scalars().all()
        assert len(admins) == 1


class TestSessionCookieSecurity:
    """Tests for session cookie creation and validation."""

    async def test_create_session_cookie_returns_string(self):
        cookie = create_session_cookie("test-user-id-123")
        assert isinstance(cookie, str)
        assert len(cookie) > 0

    async def test_decode_valid_session_cookie(self):
        user_id = "user-abc-123"
        cookie = create_session_cookie(user_id)
        payload = decode_session_cookie(cookie)
        assert payload is not None
        assert payload["user_id"] == user_id

    async def test_decode_invalid_session_cookie_returns_none(self):
        payload = decode_session_cookie("invalid-garbage-cookie-value")
        assert payload is None

    async def test_decode_tampered_session_cookie_returns_none(self):
        cookie = create_session_cookie("user-123")
        tampered = cookie[:-5] + "XXXXX"
        payload = decode_session_cookie(tampered)
        assert payload is None

    async def test_decode_expired_session_cookie_returns_none(self):
        cookie = create_session_cookie("user-123")
        payload = decode_session_cookie(cookie, max_age=0)
        assert payload is None

    async def test_decode_empty_cookie_returns_none(self):
        payload = decode_session_cookie("")
        assert payload is None


class TestAuthService:
    """Tests for AuthService business logic."""

    async def test_login_returns_user_and_cookie_on_success(
        self, db_session: AsyncSession
    ):
        hashed = get_password_hash("servicepass1")
        user = User(
            username="serviceuser",
            hashed_password=hashed,
            role="Recruiter",
        )
        db_session.add(user)
        await db_session.flush()

        auth_service = AuthService(db_session)
        result = await auth_service.login("serviceuser", "servicepass1")
        assert result is not None
        returned_user, session_cookie = result
        assert returned_user.username == "serviceuser"
        assert isinstance(session_cookie, str)
        assert len(session_cookie) > 0

    async def test_login_returns_none_on_wrong_password(
        self, db_session: AsyncSession
    ):
        hashed = get_password_hash("correctpw123")
        user = User(
            username="wrongpwservice",
            hashed_password=hashed,
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()

        auth_service = AuthService(db_session)
        result = await auth_service.login("wrongpwservice", "incorrectpw")
        assert result is None

    async def test_login_returns_none_for_nonexistent_user(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        result = await auth_service.login("nonexistent", "anypassword1")
        assert result is None

    async def test_register_creates_user_with_correct_role(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        user = await auth_service.register(
            username="reguser",
            password="registerpass1",
            full_name="Reg User",
            role="Recruiter",
        )
        assert user is not None
        assert user.username == "reguser"
        assert user.role == "Recruiter"
        assert user.full_name == "Reg User"
        assert verify_password("registerpass1", user.hashed_password)

    async def test_register_returns_none_for_duplicate_username(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        user1 = await auth_service.register(
            username="dupuser",
            password="password123",
            role="Interviewer",
        )
        assert user1 is not None

        user2 = await auth_service.register(
            username="dupuser",
            password="password456",
            role="Interviewer",
        )
        assert user2 is None

    async def test_register_returns_none_for_invalid_role(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        user = await auth_service.register(
            username="badroleuser",
            password="password123",
            role="InvalidRole",
        )
        assert user is None

    async def test_get_user_by_id_returns_user(
        self, db_session: AsyncSession
    ):
        hashed = get_password_hash("findmepass1")
        user = User(
            username="findmeuser",
            hashed_password=hashed,
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        auth_service = AuthService(db_session)
        found = await auth_service.get_user_by_id(user.id)
        assert found is not None
        assert found.username == "findmeuser"

    async def test_get_user_by_id_returns_none_for_missing(
        self, db_session: AsyncSession
    ):
        auth_service = AuthService(db_session)
        found = await auth_service.get_user_by_id("nonexistent-id-999")
        assert found is None


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    async def test_password_hash_is_not_plaintext(self):
        password = "mysecretpassword"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > len(password)

    async def test_verify_correct_password(self):
        password = "correcthorse"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    async def test_verify_incorrect_password(self):
        hashed = get_password_hash("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    async def test_different_hashes_for_same_password(self):
        password = "samepassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestProtectedRoutes:
    """Tests that protected routes require authentication."""

    async def test_dashboard_requires_auth(
        self, unauthenticated_client: httpx.AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/dashboard", follow_redirects=False
        )
        assert response.status_code == 401

    async def test_dashboard_accessible_when_authenticated(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200

    async def test_health_endpoint_does_not_require_auth(
        self, unauthenticated_client: httpx.AsyncClient
    ):
        response = await unauthenticated_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "TalentFlow ATS"