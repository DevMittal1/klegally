from typing import Optional
from fastapi import Depends, Header

from auth.exceptions.auth import (
    UnauthorizedException,
)
from auth.jwt.verification import (
    verify_access_token,
)


async def get_current_user(
    authorization: Optional[str] = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException()

    token = authorization.replace(
        "Bearer ",
        "",
    )

    # verify_access_token is a synchronous operation
    payload = verify_access_token(token)

    if not payload:
        raise UnauthorizedException()

    return payload
