from uuid import uuid4
from fastapi import HTTPException, status

from api.services.db import get_user_by_email, insert_user
from api.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, RegisterResponse

from auth.security.hashing import verify_password, hash_password
from auth.jwt.access import create_access_token, create_refresh_token
from shared_queue import QueueService, WelcomeEmailEvent


async def authenticate_user(login_data: LoginRequest) -> TokenResponse:
    # 1. Fetch user by email
    user = await get_user_by_email(login_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 2. Verify password asynchronously
    is_valid = await verify_password(login_data.password, user["hashed_password"])
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 3. Create a unique session ID
    session_id = str(uuid4())

    # 4. Generate access and refresh tokens synchronously
    access_token = create_access_token(
        user_id=user["user_id"],
        session_id=session_id,
        org_id=user["org_id"],
        role=user["role"],
    )

    refresh_token = create_refresh_token(
        user_id=user["user_id"],
        session_id=session_id,
        org_id=user["org_id"],
        role=user["role"],
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def register_user(
    register_data: RegisterRequest,
    queue: QueueService,
) -> RegisterResponse:
    """
    Registers a new user in KLegally MongoDB database, hashes their password,
    and publishes a welcome email task to our abstract QueueService.
    """
    # 1. Check if user already exists
    existing_user = await get_user_by_email(register_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # 2. Hash password asynchronously ( Argon2 Thread Hand-off )
    hashed = await hash_password(register_data.password)

    # 3. Generate a clean unique user ID
    user_id = f"user_{str(uuid4())[:8]}"

    # 4. Store user in MongoDB collection
    new_user = {
        "user_id": user_id,
        "email": register_data.email.lower(),
        "hashed_password": hashed,
        "role": register_data.role,
        "org_id": register_data.org_id,
    }
    await insert_user(new_user)

    # 5. Publish registration event to Queue using standard interface contract
    event = WelcomeEmailEvent(user_id=user_id, email=register_data.email)
    await queue.publish("email_tasks", event.model_dump())

    return RegisterResponse(
        user_id=user_id,
        email=register_data.email,
        role=register_data.role,
        org_id=register_data.org_id,
    )
