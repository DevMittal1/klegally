from abc import ABC, abstractmethod


class QueueService(ABC):
    @abstractmethod
    async def publish(self, topic: str, payload: dict) -> None:
        """Publish a payload to a specific topic/stream asynchronously."""
        pass
