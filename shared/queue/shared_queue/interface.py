from abc import ABC, abstractmethod


class QueueService(ABC):
    @abstractmethod
    async def publish(self, topic: str, payload: dict) -> None:
        """Publish a payload to a specific topic/stream asynchronously."""
        pass

    @abstractmethod
    async def create_consumer_group(self, stream: str, group: str) -> None:
        """Create a consumer group for a stream asynchronously, ensuring it exists."""
        pass
