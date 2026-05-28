from redis.asyncio import Redis
from api.config import api_settings
from shared_queue import QueueService, RedisStreamQueue

# Initialize global Redis client using the latest async redis driver
redis_client = Redis.from_url(api_settings.REDIS_URL, decode_responses=True)

# Instantiate the concrete RedisStreamQueue adapter
redis_stream_queue = RedisStreamQueue(redis_client)


def get_queue_service() -> QueueService:
    """
    FastAPI dependency injection provider for QueueService interface.
    Returns the concrete RedisStreamQueue adapter.
    """
    return redis_stream_queue


async def close_redis_connection() -> None:
    """Close the underlying Redis client connection pool on server shutdown."""
    await redis_client.close()
