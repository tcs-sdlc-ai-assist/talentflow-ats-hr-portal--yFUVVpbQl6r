import asyncio
from collections.abc import AsyncGenerator
from typing import Optional

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_session_cookie, get_password_hash
from app.main import app
from app.models.user import User


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for tests."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override the get_db dependency to use the test database."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an async HTTP client for testing."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def _create_user(
    db: AsyncSession,
    username: str,
    password: str,
    role: str,
    full_name: str = "",
) -> User:
    """Helper to create a user in the test database."""
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an Admin user."""
    return await _create_user(
        db=db_session,
        username="testadmin",
        password="adminpass123",
        role="Admin",
        full_name="Test Admin",
    )


@pytest_asyncio.fixture
async def hiring_manager_user(db_session: AsyncSession) -> User:
    """Create a Hiring Manager user."""
    return await _create_user(
        db=db_session,
        username="testhiringmgr",
        password="hmpass12345",
        role="Hiring Manager",
        full_name="Test Hiring Manager",
    )


@pytest_asyncio.fixture
async def recruiter_user(db_session: AsyncSession) -> User:
    """Create a Recruiter user."""
    return await _create_user(
        db=db_session,
        username="testrecruiter",
        password="recruiterpass1",
        role="Recruiter",
        full_name="Test Recruiter",
    )


@pytest_asyncio.fixture
async def interviewer_user(db_session: AsyncSession) -> User:
    """Create an Interviewer user."""
    return await _create_user(
        db=db_session,
        username="testinterviewer",
        password="interviewpass1",
        role="Interviewer",
        full_name="Test Interviewer",
    )


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession) -> User:
    """Create a Viewer user."""
    return await _create_user(
        db=db_session,
        username="testviewer",
        password="viewerpass123",
        role="Viewer",
        full_name="Test Viewer",
    )


def _make_authenticated_cookies(user: User) -> dict[str, str]:
    """Generate session cookies for a given user."""
    session_cookie = create_session_cookie(user.id)
    return {"session": session_cookie}


@pytest_asyncio.fixture
async def admin_client(
    client: httpx.AsyncClient,
    admin_user: User,
) -> httpx.AsyncClient:
    """Provide an authenticated client with Admin role."""
    client.cookies.update(_make_authenticated_cookies(admin_user))
    return client


@pytest_asyncio.fixture
async def hiring_manager_client(
    admin_user: User,
    hiring_manager_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated client with Hiring Manager role."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        ac.cookies.update(_make_authenticated_cookies(hiring_manager_user))
        yield ac


@pytest_asyncio.fixture
async def recruiter_client(
    admin_user: User,
    recruiter_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated client with Recruiter role."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        ac.cookies.update(_make_authenticated_cookies(recruiter_user))
        yield ac


@pytest_asyncio.fixture
async def interviewer_client(
    admin_user: User,
    interviewer_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated client with Interviewer role."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        ac.cookies.update(_make_authenticated_cookies(interviewer_user))
        yield ac


@pytest_asyncio.fixture
async def viewer_client(
    admin_user: User,
    viewer_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an authenticated client with Viewer role."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        ac.cookies.update(_make_authenticated_cookies(viewer_user))
        yield ac


@pytest_asyncio.fixture
async def unauthenticated_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an unauthenticated HTTP client."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac