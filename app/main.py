import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import async_session_factory, create_all_tables
from app.routers import (
    applications_router,
    auth_router,
    candidates_router,
    dashboard_router,
    interviews_router,
    jobs_router,
    landing_router,
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TalentFlow ATS...")

    await create_all_tables()
    logger.info("Database tables created/verified.")

    async with async_session_factory() as session:
        try:
            auth_service = AuthService(session)
            await auth_service.seed_default_admin()
            await session.commit()
            logger.info("Default admin user seeded.")
        except Exception as e:
            await session.rollback()
            logger.error("Failed to seed default admin user: %s", e)

    logger.info("TalentFlow ATS startup complete.")
    yield
    logger.info("TalentFlow ATS shutting down.")


app = FastAPI(
    title="TalentFlow ATS",
    description="Applicant Tracking System",
    version="1.0.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class TemplateContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        return response


app.add_middleware(TemplateContextMiddleware)

app.include_router(auth_router)
app.include_router(landing_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(applications_router)
app.include_router(interviews_router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "TalentFlow ATS"}