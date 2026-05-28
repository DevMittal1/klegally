from pydantic import BaseModel, EmailStr


class WelcomeEmailEvent(BaseModel):
    user_id: str
    email: EmailStr
