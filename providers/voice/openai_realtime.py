from __future__ import annotations

from livekit.plugins import openai

from config.settings import Settings


class OpenAIRealtimeVoiceFactory:
    """Adapter around LiveKit's OpenAI Realtime plugin."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_realtime_model(self) -> openai.realtime.RealtimeModel:
        return openai.realtime.RealtimeModel(
            model=self._settings.openai_realtime_model,
            voice=self._settings.openai_realtime_voice,
        )
