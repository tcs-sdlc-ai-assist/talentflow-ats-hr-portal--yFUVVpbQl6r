import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/login")
async def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        context={"user": None, "error": None, "username": ""},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)

    if not username or not username.strip():
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "Username is required.",
                "username": username,
            },
            status_code=400,
        )

    if not password:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "Password is required.",
                "username": username,
            },
            status_code=400,
        )

    result = await auth_service.login(username.strip(), password)

    if result is None:
        logger.info("Failed login attempt for username='%s'", username)
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "user": None,
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=401,
        )

    user, session_cookie = result

    logger.info("Successful login for user_id=%s username='%s'", user.id, user.username)

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=session_cookie,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response


@router.get("/register")
async def register_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        context={
            "user": None,
            "error": None,
            "errors": None,
            "username": "",
        },
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    errors: list[str] = []

    username_stripped = username.strip() if username else ""

    if not username_stripped:
        errors.append("Username is required.")

    if len(username_stripped) < 3:
        errors.append("Username must be at least 3 characters long.")

    if username_stripped and not all(
        c.isalnum() or c in ("_", "-", ".") for c in username_stripped
    ):
        errors.append(
            "Username must contain only alphanumeric characters, underscores, hyphens, or dots."
        )

    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters long.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": None,
                "errors": errors,
                "username": username_stripped,
            },
            status_code=400,
        )

    user = await auth_service.register(
        username=username_stripped,
        password=password,
        full_name="",
        role="Interviewer",
    )

    if user is None:
        logger.info("Registration failed: username '%s' already exists", username_stripped)
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "user": None,
                "error": f"Username '{username_stripped}' is already taken. Please choose a different one.",
                "errors": None,
                "username": username_stripped,
            },
            status_code=400,
        )

    logger.info(
        "New user registered: user_id=%s username='%s' role='%s'",
        user.id,
        user.username,
        user.role,
    )

    from app.core.security import create_session_cookie

    session_cookie = create_session_cookie(user.id)

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=session_cookie,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    logger.info("User logged out")
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(key="session", path="/")
    return response