from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    livekit_url: str = Field(default="", alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field(default="voice-receptionist", alias="LIVEKIT_AGENT_NAME")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    default_business_id: str = Field(default="demo_salon", alias="DEFAULT_BUSINESS_ID")
    business_config_dir: Path = Field(
        default=Path("config/businesses"), alias="BUSINESS_CONFIG_DIR"
    )

    database_url: str = Field(
        default="sqlite+pysqlite:///./receptionist.db",
        alias="DATABASE_URL",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    log_transcripts: bool = Field(default=False, alias="LOG_TRANSCRIPTS")
    otel_exporter_otlp_endpoint: str = Field(default="", alias="OTEL_EXPORTER_OTLP_ENDPOINT")

    call_metadata_retention_days: int = Field(default=90, alias="CALL_METADATA_RETENTION_DAYS")
    phone_number_business_map: dict[str, str] = Field(
        default_factory=dict, alias="PHONE_NUMBER_BUSINESS_MAP"
    )
    human_handoff_destination: str = Field(default="", alias="HUMAN_HANDOFF_DESTINATION")

    run_livekit_integration: bool = Field(default=False, alias="RUN_LIVEKIT_INTEGRATION")

    openai_realtime_model: str = Field(default="gpt-4o-realtime-preview", alias="OPENAI_REALTIME_MODEL")
    openai_realtime_voice: str = Field(default="marin", alias="OPENAI_REALTIME_VOICE")

    @field_validator("phone_number_business_map", mode="before")
    @classmethod
    def parse_phone_map(cls, value: Any) -> dict[str, str]:
        if value is None or value == "":
            return {}
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("PHONE_NUMBER_BUSINESS_MAP must be a JSON object")
            return {str(k): str(v) for k, v in parsed.items()}
        raise ValueError("Invalid PHONE_NUMBER_BUSINESS_MAP")


@lru_cache
def get_settings() -> Settings:
    return Settings()
