from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from auth.exceptions.auth import (
    UnauthorizedException,
)
from auth.jwt.verification import (
    verify_access_token,
)

# Standard OAuth2 scheme specifying standard login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
):
    # Verify the Bearer token
    payload = verify_access_token(token)

    if not payload:
        raise UnauthorizedException()

    return payload
