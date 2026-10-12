from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsSnapshot:
    counters: dict[str, int]
    events: list[dict[str, Any]]


class CallMetrics:
    """Thread-safe in-process counters for call lifecycle (no PII in tags)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._events: list[dict[str, Any]] = []

    def increment(self, name: str, *, value: int = 1, **tags: str) -> None:
        key = _counter_key(name, tags)
        with self._lock:
            self._counters[key] += value

    def record_event(self, name: str, **fields: Any) -> None:
        payload = {"event": name, **fields}
        with self._lock:
            self._events.append(payload)

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                counters=dict(self._counters),
                events=list(self._events),
            )

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._events.clear()


_metrics = CallMetrics()


def get_metrics() -> CallMetrics:
    return _metrics


def _counter_key(name: str, tags: dict[str, str]) -> str:
    if not tags:
        return name
    ordered = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
    return f"{name}|{ordered}"
