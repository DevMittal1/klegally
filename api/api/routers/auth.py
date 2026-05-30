from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

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
async def login(
    request: Request,
):
    """
    Authenticate a user and return access and refresh tokens.
    Supports both standard JSON payloads (LoginRequest) and Form URL-encoded data
    (such as FastAPI Swagger UI /docs Authorize logins using standard OAuth2 specs).
    """
    content_type = request.headers.get("content-type", "")
    email = None
    password = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )
    else:
        # Parse Form URL-encoded parameters
        try:
            form = await request.form()
            email = form.get("username")  # OAuth2 standard Form maps email to username
            password = form.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid form data payload",
            )

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing email (username) or password",
        )

    # Instantiate LoginRequest schema internally and call the service
    login_data = LoginRequest(email=email, password=password)
    return await authenticate_user(login_data)


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
