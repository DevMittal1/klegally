from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse, RegisterRequest, RegisterResponse
from api.services.auth import authenticate_user, register_user
from api.infrastructure.queue import get_queue_service

from auth.jwt.verification import verify_refresh_token
from auth.jwt.access import create_access_token
from shared_queue import QueueService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    queue: Annotated[QueueService, Depends(get_queue_service)],
):
    """
    Register a new user in the KLegally platform.
    This hashes their password, records their profile, and schedules
    a welcome email event via our decoupled QueueService.
    """
    return await register_user(request, queue)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate a user and return access and refresh tokens.
    """
    return await authenticate_user(request)


@router.post("/refresh")
async def refresh(request: RefreshTokenRequest):
    """
    Exchange a valid refresh token for a brand new access token.
    """
    # verify_refresh_token is synchronous
    payload = verify_refresh_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # create_access_token is synchronous
    new_access_token = create_access_token(
        user_id=payload["sub"],
        session_id=payload["sid"],
        org_id=payload["org_id"],
        role=payload["role"],
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }
