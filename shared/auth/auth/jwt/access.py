from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from auth.config import settings
from auth.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE


def create_access_token(
    *,
    user_id: str,
    session_id: str,
    org_id: str,
    role: str,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "sid": session_id,
        "org_id": org_id,
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(
            (
                now
                + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            ).timestamp()
        ),
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    *,
    user_id: str,
    session_id: str,
    org_id: str,
    role: str,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "sid": session_id,
        "org_id": org_id,
        "role": role,
        "type": REFRESH_TOKEN_TYPE,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(
            (
                now
                + timedelta(
                    days=settings.REFRESH_TOKEN_EXPIRE_DAYS
                )
            ).timestamp()
        ),
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
