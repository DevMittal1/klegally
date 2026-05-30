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

    async def create_consumer_group(self, stream: str, group: str) -> None:
        """
        Creates a consumer group for the specified stream asynchronously.
        Catches BUSYGROUP error if the consumer group already exists.
        """
        try:
            # mkstream=True automatically creates the stream if it doesn't exist
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
            print(f"Consumer group '{group}' created successfully for stream '{stream}'.")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                # The consumer group already exists, safe to ignore
                print(f"Consumer group '{group}' already exists for stream '{stream}'.")
            else:
                print(f"Warning: consumer group creation '{group}' for '{stream}' failed: {e}")
