"""Simple in-memory pub/sub for streaming agent messages to WebSocket clients."""

import asyncio
from collections import defaultdict
from typing import Dict, Set

from core.logging_config import get_logger

logger = get_logger("compsphere.message_bus")


class MessageBus:
    """Manages per-task message queues for WebSocket subscribers."""

    def __init__(self):
        # task_id -> set of asyncio.Queue
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[task_id].add(queue)
        logger.debug(
            f"Subscriber added for task {task_id[:8]} "
            f"(total={len(self._subscribers[task_id])})"
        )
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        self._subscribers[task_id].discard(queue)
        if not self._subscribers[task_id]:
            del self._subscribers[task_id]

    async def publish(self, task_id: str, message: dict):
        for queue in list(self._subscribers.get(task_id, [])):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for task {task_id[:8]}, dropping message")


# Singleton
message_bus = MessageBus()
