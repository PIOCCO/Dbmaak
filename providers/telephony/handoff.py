from __future__ import annotations

from typing import Protocol

from livekit.agents import JobContext

from agent.context import SessionContext


class TelephonyHandoffProvider(Protocol):
    async def transfer_to_human(
        self, job_ctx: JobContext, session_ctx: SessionContext, *, reason: str
    ) -> tuple[bool, str]: ...
