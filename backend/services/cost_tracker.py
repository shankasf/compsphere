"""Real-time cost tracking and broadcasting for admin dashboard."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Set

from core.logging_config import get_logger

logger = get_logger("compsphere.cost_tracker")

# LLM Pricing per 1M tokens (USD)
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
        "name": "Claude Sonnet 4",
    },
    "claude-opus-4-20250514": {
        "input": 15.00, "output": 75.00,
        "cache_read": 1.50, "cache_write": 18.75,
        "name": "Claude Opus 4",
    },
    "claude-haiku-3-5-20241022": {
        "input": 0.80, "output": 4.00,
        "cache_read": 0.08, "cache_write": 1.00,
        "name": "Claude Haiku 3.5",
    },
    "claude-code-sdk": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
        "name": "Claude Code (Sonnet)",
    },
}

class CostTracker:
    """Tracks LLM and compute costs, broadcasts updates to admin WebSocket subscribers."""

    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()
        self._cumulative_cost: float = 0.0
        self._cumulative_input_tokens: int = 0
        self._cumulative_output_tokens: int = 0
        self._cumulative_cache_read_tokens: int = 0
        self._cumulative_cache_creation_tokens: int = 0

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        logger.debug(f"Admin cost subscriber added (total={len(self._subscribers)})")
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    async def record_usage(
        self,
        session_id: str,
        task_id: str,
        user_id: str,
        total_cost_usd: float,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        duration_ms: int = 0,
        num_turns: int = 0,
    ):
        """Record a usage event and broadcast to admin subscribers."""
        self._cumulative_cost += total_cost_usd
        self._cumulative_input_tokens += input_tokens
        self._cumulative_output_tokens += output_tokens
        self._cumulative_cache_read_tokens += cache_read_tokens
        self._cumulative_cache_creation_tokens += cache_creation_tokens

        update = {
            "type": "cost_update",
            "session_id": session_id,
            "task_id": task_id,
            "user_id": user_id,
            "cost_usd": round(total_cost_usd, 6),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_creation_tokens": cache_creation_tokens,
            "duration_ms": duration_ms,
            "num_turns": num_turns,
            "cumulative_cost": round(self._cumulative_cost, 6),
            "cumulative_input_tokens": self._cumulative_input_tokens,
            "cumulative_output_tokens": self._cumulative_output_tokens,
            "cumulative_cache_read_tokens": self._cumulative_cache_read_tokens,
            "cumulative_cache_creation_tokens": self._cumulative_cache_creation_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Usage recorded: session={session_id[:8]} cost=${total_cost_usd:.4f} "
            f"tokens={input_tokens}in/{output_tokens}out "
            f"cache={cache_read_tokens}read/{cache_creation_tokens}write"
        )

        await self._broadcast(update)

    async def _broadcast(self, data: dict):
        for q in list(self._subscribers):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning("Admin cost subscriber queue full, dropping message")

    def calculate_cache_savings(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_creation_tokens: int,
        model: str = "claude-code-sdk",
    ) -> dict:
        """Calculate actual cost vs. no-cache cost and savings.

        Returns dict with actual_cost, no_cache_cost, savings, cache_hit_rate.
        """
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-code-sdk"])
        per_m = 1_000_000

        # Actual cost with caching
        actual_cost = (
            (input_tokens / per_m) * pricing["input"]
            + (output_tokens / per_m) * pricing["output"]
            + (cache_read_tokens / per_m) * pricing["cache_read"]
            + (cache_creation_tokens / per_m) * pricing["cache_write"]
        )

        # Hypothetical cost if all cache tokens were regular input tokens
        total_input_if_no_cache = input_tokens + cache_read_tokens + cache_creation_tokens
        no_cache_cost = (
            (total_input_if_no_cache / per_m) * pricing["input"]
            + (output_tokens / per_m) * pricing["output"]
        )

        savings = no_cache_cost - actual_cost

        # Cache hit rate: fraction of total input-side tokens served from cache
        total_input_side = input_tokens + cache_read_tokens + cache_creation_tokens
        cache_hit_rate = (
            cache_read_tokens / total_input_side if total_input_side > 0 else 0.0
        )

        return {
            "actual_cost": round(actual_cost, 6),
            "no_cache_cost": round(no_cache_cost, 6),
            "savings": round(savings, 6),
            "cache_hit_rate": round(cache_hit_rate, 4),
        }

    def get_cumulative(self) -> dict:
        return {
            "cumulative_cost": round(self._cumulative_cost, 6),
            "cumulative_input_tokens": self._cumulative_input_tokens,
            "cumulative_output_tokens": self._cumulative_output_tokens,
            "cumulative_cache_read_tokens": self._cumulative_cache_read_tokens,
            "cumulative_cache_creation_tokens": self._cumulative_cache_creation_tokens,
        }


# Singleton
cost_tracker = CostTracker()
