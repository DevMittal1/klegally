import os
import sys
import asyncio
from typing import Optional
from pydantic_settings import BaseSettings
from redis.asyncio import Redis
from motor.motor_asyncio import AsyncIOMotorClient

# Add local path and shared queue path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"),
)

from worker.infrastructure.queue.poller import run_ingestion_workers
from worker.ingestion import DocumentIngestionPipeline
from shared_queue import RedisStreamQueue


class IngestionWorkerSettings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "klegally"

    # S3 configurations
    S3_BUCKET: str = "klegally-documents"
    S3_ENDPOINT_URL: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    class Config:
        env_file = [".env", "../.env", "../../.env", "../../../.env"]
        extra = "ignore"


async def main():
    settings = IngestionWorkerSettings()
    print("=" * 60)
    print(" KLEGALLY ASYNC INGESTION WORKER BOOTING UP")
    print(f" Redis Broker: {settings.REDIS_URL}")
    print(f" MongoDB URL:  {settings.MONGODB_URL}")
    print(f" S3 Bucket:    {settings.S3_BUCKET}")
    print("=" * 60)

    # 1. Establish connection to Redis & MongoDB
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    mongo_client = AsyncIOMotorClient(
        settings.MONGODB_URL, serverSelectionTimeoutMS=2000
    )
    db = mongo_client[settings.MONGODB_DB_NAME]

    # 2. Setup Queue Service and Ingestion Pipeline
    queue_service = RedisStreamQueue(redis_client)
    storage_settings = {
        "S3_BUCKET": settings.S3_BUCKET,
        "S3_ENDPOINT_URL": settings.S3_ENDPOINT_URL,
        "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
        "AWS_REGION": settings.AWS_REGION,
    }

    pipeline = DocumentIngestionPipeline(db, queue_service, storage_settings)

    try:
        # Pre-create all consumer groups to ensure safe execution
        await queue_service.create_consumer_group("document:parse", "parse-group")
        await queue_service.create_consumer_group("document:chunk", "chunk-group")
        await queue_service.create_consumer_group("document:embed", "embed-group")

        # 3. Start concurrent ingestion pollers in the foreground (blocks)
        await run_ingestion_workers(redis_client, pipeline, queue_service, db)

    finally:
        # 4. Close connections cleanly on shutdown
        await redis_client.close()
        mongo_client.close()
        print("Redis and MongoDB ingestion worker connections closed cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nIngestion worker shutdown requested by user.")
