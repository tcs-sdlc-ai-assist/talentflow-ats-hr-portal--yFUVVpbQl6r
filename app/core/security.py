import logging
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Error verifying password: %s", e)
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_session_cookie(user_id: str) -> str:
    return serializer.dumps({"user_id": user_id}, salt="session")


def decode_session_cookie(
    cookie: str,
    max_age: Optional[int] = None,
) -> Optional[dict]:
    if max_age is None:
        max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    try:
        data = serializer.loads(cookie, salt="session", max_age=max_age)
        if not isinstance(data, dict) or "user_id" not in data:
            logger.warning("Invalid session cookie payload")
            return None
        return data
    except SignatureExpired:
        logger.info("Session cookie has expired")
        return None
    except BadSignature:
        logger.warning("Invalid session cookie signature")
        return None
    except Exception as e:
        logger.error("Unexpected error decoding session cookie: %s", e)
        return None