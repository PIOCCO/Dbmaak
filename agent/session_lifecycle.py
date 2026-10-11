from __future__ import annotations

import threading
from collections.abc import Callable

from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


class CallSessionFinalizer:
    """Idempotent call/session cleanup (safe if invoked multiple times)."""

    def __init__(
        self,
        *,
        call_id: str,
        business_id: str,
        on_finalize: Callable[[str], None],
    ) -> None:
        self._call_id = call_id
        self._business_id = business_id
        self._on_finalize = on_finalize
        self._lock = threading.Lock()
        self._finalized = False
        self._final_status: str | None = None

    def finalize(self, status: str = "completed") -> None:
        with self._lock:
            if self._finalized:
                logger.debug(
                    "session_finalize_skipped",
                    call_id=self._call_id,
                    business_id=self._business_id,
                    prior_status=self._final_status,
                    attempted_status=status,
                )
                return
            self._finalized = True
            self._final_status = status

        get_metrics().increment("session_ended", business_id=self._business_id)
        get_metrics().record_event(
            "call_lifecycle",
            phase="ended",
            business_id=self._business_id,
            call_id=self._call_id,
            status=status,
        )
        try:
            self._on_finalize(status)
        except Exception:
            logger.exception(
                "session_finalize_failed",
                call_id=self._call_id,
                business_id=self._business_id,
            )
            raise
