from __future__ import annotations

from config.settings import Settings
from providers.voice.azure_realtime import AzureRealtimeVoiceFactory
from providers.voice.base import VoiceModelFactory


def build_voice_factory(settings: Settings) -> VoiceModelFactory:
    """Select the configured voice provider (Azure OpenAI Realtime only)."""
    return AzureRealtimeVoiceFactory(settings)
