import jwt
from jwt import InvalidTokenError
from typing import Optional, Dict, Any

from auth.config import settings
from auth.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )

        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None

        return payload

    except InvalidTokenError:
        return None


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )

        if payload.get("type") != REFRESH_TOKEN_TYPE:
            return None

        return payload

    except InvalidTokenError:
        return None
