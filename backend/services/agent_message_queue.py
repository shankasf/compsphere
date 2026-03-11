import asyncio
from typing import Optional

from core.logging_config import get_logger

logger = get_logger("compsphere.agent_queue")


class AgentMessageQueueRegistry:
    """Registry mapping task_id -> asyncio.Queue for follow-up messages."""

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def create(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[task_id] = queue
        logger.debug(f"Message queue created for task {task_id[:8]}")
        return queue

    def get(self, task_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(task_id)

    def remove(self, task_id: str):
        self._queues.pop(task_id, None)
        logger.debug(f"Message queue removed for task {task_id[:8]}")


# Singleton
agent_message_queue_registry = AgentMessageQueueRegistry()
