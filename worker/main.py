import os
import sys
import asyncio
from typing import Optional
from pydantic_settings import BaseSettings
from redis.asyncio import Redis

# Add local path and shared queue path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"),
)

from worker.handlers import SendWelcomeEmailHandler
from worker.infrastructure.email.mailjet import MailjetEmailProvider
from worker.infrastructure.queue.poller import run_worker


class WorkerSettings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"

    # Optional Mailjet configuration keys
    MJ_APIKEY_PUBLIC: Optional[str] = None
    MJ_APIKEY_PRIVATE: Optional[str] = None
    MJ_SENDER_EMAIL: Optional[str] = None

    class Config:
        env_file = [".env", "../.env", "../../.env", "../../../.env"]
        extra = "ignore"


async def main():
    settings = WorkerSettings()
    print("=" * 60)
    print(" KLEGALLY BACKGROUND WORKER BOOTING UP")
    print(f" Redis Broker: {settings.REDIS_URL}")

    # 1. Dependency Injection setup
    email_provider = None
    if (
        settings.MJ_APIKEY_PUBLIC
        and settings.MJ_APIKEY_PRIVATE
        and settings.MJ_SENDER_EMAIL
    ):
        print("[Mailer] Injecting Async MailjetEmailProvider...")
        email_provider = MailjetEmailProvider(
            api_key_public=settings.MJ_APIKEY_PUBLIC,
            api_key_private=settings.MJ_APIKEY_PRIVATE,
            sender_email=settings.MJ_SENDER_EMAIL,
        )

    print("=" * 60)

    email_handler = SendWelcomeEmailHandler(email_provider)

    # 2. Establish connection to Redis
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        # 3. Start polling tasks asynchronously
        await run_worker(redis_client, email_handler)
    finally:
        # 4. Close connection cleanly on shutdown
        await redis_client.close()
        print("Redis worker connection closed cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWorker shutdown requested by user.")
