from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    JWT_PRIVATE_KEY: str
    JWT_PUBLIC_KEY: str

    JWT_ALGORITHM: str = "RS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    JWT_ISSUER: str = "auth-service"
    JWT_AUDIENCE: str = "api-gateway"

    class Config:
        # Search locally, parent folder (monorepo root), or grandfather folders
        env_file = [".env", "../.env", "../../.env", "../../../.env"]
        extra = "ignore"


settings = Settings()
