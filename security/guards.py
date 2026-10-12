from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class IdempotencyStore:
    """In-memory idempotency keys scoped to a call session."""

    _keys: set[str] = field(default_factory=set)

    def claim(self, key: str) -> bool:
        if key in self._keys:
            return False
        self._keys.add(key)
        return True


@dataclass
class CallToolGuard:
    max_calls_per_tool: int = 8
    max_total_calls: int = 40
    min_interval_seconds: float = 0.25

    _tool_counts: dict[str, int] = field(default_factory=dict)
    _total_calls: int = 0
    _last_call_monotonic: float = 0.0

    def check_and_record(self, tool_name: str) -> None:
        now = time.monotonic()
        if self._last_call_monotonic and (now - self._last_call_monotonic) < self.min_interval_seconds:
            raise RuntimeError("Tool calls are arriving too quickly; please wait a moment.")
        self._last_call_monotonic = now

        self._total_calls += 1
        if self._total_calls > self.max_total_calls:
            raise RuntimeError("Too many tool calls in this call session.")

        count = self._tool_counts.get(tool_name, 0) + 1
        self._tool_counts[tool_name] = count
        if count > self.max_calls_per_tool:
            raise RuntimeError(f"Tool '{tool_name}' was called too many times.")
