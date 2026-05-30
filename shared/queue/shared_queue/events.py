from pydantic import BaseModel, EmailStr


class WelcomeEmailEvent(BaseModel):
    user_id: str
    email: EmailStr


class ParseEvent(BaseModel):
    document_id: str
    attempt: int = 1


class ChunkEvent(BaseModel):
    document_id: str
    attempt: int = 1


class EmbedEvent(BaseModel):
    document_id: str
    attempt: int = 1


class FailedEvent(BaseModel):
    document_id: str
    stage: str
    error: str
    attempt: int = 1
