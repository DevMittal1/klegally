import json
from redis.asyncio import Redis
from shared_queue.interface import QueueService


class RedisStreamQueue(QueueService):
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def publish(self, topic: str, payload: dict) -> None:
        """
        Publishes a message to a Redis Stream asynchronously.
        Serializes the nested payload dictionary into a flat string format.
        """
        serialized_payload = {"payload": json.dumps(payload)}
        # xadd sends the serialized payload to the specified Redis Stream/Topic
        await self.redis.xadd(topic, serialized_payload)
