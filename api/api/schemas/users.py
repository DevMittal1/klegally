from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    role: str
    org_id: str
