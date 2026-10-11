from __future__ import annotations

from livekit.plugins import openai

from config.azure_auth import resolve_azure_realtime_credentials
from config.settings import Settings


class AzureRealtimeVoiceFactory:
    """Azure OpenAI Realtime speech-to-speech via LiveKit's OpenAI plugin (Azure mode)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_realtime_model(self) -> openai.realtime.RealtimeModel:
        api_key, entra_token = resolve_azure_realtime_credentials(self._settings)
        api_version = self._settings.azure_openai_api_version.strip() or None

        kwargs: dict = {
            "azure_deployment": self._settings.azure_openai_deployment.strip(),
            "azure_endpoint": self._settings.azure_openai_endpoint.strip(),
            "voice": self._settings.azure_openai_voice.strip(),
            "api_key": api_key,
            "entra_token": entra_token,
        }
        if api_version:
            kwargs["api_version"] = api_version

        return openai.realtime.RealtimeModel.with_azure(**kwargs)
