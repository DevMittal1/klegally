from pydantic import BaseModel


class AccessTokenPayload(BaseModel):
    sub: str
    sid: str
    org_id: str
    role: str

    type: str

    iss: str
    aud: str

    iat: int
    exp: int
    jti: str


class RefreshTokenPayload(BaseModel):
    sub: str
    sid: str
    org_id: str
    role: str

    type: str

    iss: str
    aud: str

    iat: int
    exp: int
    jti: str
