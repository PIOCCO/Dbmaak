from __future__ import annotations

from typing import Protocol

from livekit.agents import llm


class VoiceModelFactory(Protocol):
    def create_realtime_model(self) -> llm.RealtimeModel: ...
