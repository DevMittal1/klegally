from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.users import UserResponse
from api.services.db import get_user_by_id

from auth.dependencies.current_user import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Returns the authenticated user details from the DB.
    Requires a valid JWT token in the 'Authorization: Bearer <token>' header.
    """
    user = await get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        role=user["role"],
        org_id=user["org_id"],
    )
