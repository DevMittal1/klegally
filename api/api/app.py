from fastapi import FastAPI

from api.config import api_settings
from api.routers import auth, users, documents
from api.services.db import seed_database
from api.infrastructure.queue import close_redis_connection

from auth.middleware.auth_context import AuthContextMiddleware

app = FastAPI(
    title=api_settings.PROJECT_NAME,
    description="Backend API Service for KLegally with modular layout and Async Shared Auth",
    version="0.1.0"
)

# Mount context propagation middleware
app.add_middleware(AuthContextMiddleware)


@app.on_event("startup")
async def startup_event():
    await seed_database()


@app.on_event("shutdown")
async def shutdown_event():
    await close_redis_connection()


# Include sub-routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to KLegally Modular API Service",
        "status": "online",
        "auth_enabled": True,
        "features": ["async_auth", "refresh_tokens", "modular_architecture", "mongodb", "redis_streams"]
    }
