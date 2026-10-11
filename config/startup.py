from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from business.registry import BusinessRegistry


class ConfigurationError(RuntimeError):
    pass


def validate_common(settings: Settings) -> None:
    if not settings.business_config_dir.exists():
        raise ConfigurationError(
            f"BUSINESS_CONFIG_DIR does not exist: {settings.business_config_dir}"
        )
    registry = BusinessRegistry.from_directory(settings.business_config_dir)
    if not registry.list_ids():
        raise ConfigurationError("No business profiles found in BUSINESS_CONFIG_DIR.")
    if settings.default_business_id not in registry.list_ids():
        raise ConfigurationError(
            f"DEFAULT_BUSINESS_ID '{settings.default_business_id}' is not a loaded business profile."
        )
    for phone, business_id in settings.phone_number_business_map.items():
        if business_id not in registry.list_ids():
            raise ConfigurationError(
                f"PHONE_NUMBER_BUSINESS_MAP references unknown business '{business_id}' for {phone}."
            )


def validate_for_console(settings: Settings) -> None:
    validate_common(settings)
    if not settings.openai_api_key.strip():
        raise ConfigurationError(
            "Missing OPENAI_API_KEY for console mode. Add it to .env (see .env.example)."
        )
    from config.openai_preflight import OpenAIPreflightError, preflight_enabled, preflight_openai_realtime

    if preflight_enabled():
        try:
            preflight_openai_realtime(settings)
        except OpenAIPreflightError as exc:
            raise ConfigurationError(str(exc)) from exc


def validate_for_worker(settings: Settings) -> None:
    validate_common(settings)
    missing: list[str] = []
    if not settings.livekit_url.strip():
        missing.append("LIVEKIT_URL")
    if not settings.livekit_api_key.strip():
        missing.append("LIVEKIT_API_KEY")
    if not settings.livekit_api_secret.strip():
        missing.append("LIVEKIT_API_SECRET")
    if not settings.openai_api_key.strip():
        missing.append("OPENAI_API_KEY")
    if missing:
        raise ConfigurationError(
            "Missing required environment variables for voice worker: "
            + ", ".join(missing)
            + ". See .env.example."
        )


def validate_database_url(settings: Settings) -> None:
    url = settings.database_url
    if url.startswith("sqlite"):
        return
    if not url.startswith("postgresql"):
        raise ConfigurationError(
            "DATABASE_URL must be sqlite (dev) or postgresql+psycopg (production target)."
        )
