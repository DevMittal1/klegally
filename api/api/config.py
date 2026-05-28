from pydantic_settings import BaseSettings


class ApiSettings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    PROJECT_NAME: str = "KLegally API Service"

    # MongoDB configurations
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "klegally"

    # Redis configurations
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        # Search locally, parent folder (monorepo root), or grandfather folders
        env_file = [".env", "../.env", "../../.env", "../../../.env"]
        extra = "ignore"


api_settings = ApiSettings()
