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


def _validate_azure_voice(settings: Settings) -> None:
    from config.azure_preflight import AzurePreflightError, preflight_enabled, preflight_azure_realtime
    from config.azure_validation import AzureConfigError, validate_azure_openai_config

    try:
        validate_azure_openai_config(settings)
    except AzureConfigError as exc:
        raise ConfigurationError(str(exc)) from exc

    if preflight_enabled():
        try:
            preflight_azure_realtime(settings)
        except AzurePreflightError as exc:
            raise ConfigurationError(str(exc)) from exc


def validate_for_console(settings: Settings) -> None:
    validate_common(settings)
    _validate_azure_voice(settings)


def validate_for_worker(settings: Settings) -> None:
    validate_common(settings)
    missing: list[str] = []
    if not settings.livekit_url.strip():
        missing.append("LIVEKIT_URL")
    if not settings.livekit_api_key.strip():
        missing.append("LIVEKIT_API_KEY")
    if not settings.livekit_api_secret.strip():
        missing.append("LIVEKIT_API_SECRET")
    if missing:
        raise ConfigurationError(
            "Missing required environment variables for voice worker: "
            + ", ".join(missing)
            + ". See .env.example."
        )
    _validate_azure_voice(settings)


def validate_database_url(settings: Settings) -> None:
    url = settings.database_url
    if url.startswith("sqlite"):
        return
    if not url.startswith("postgresql"):
        raise ConfigurationError(
            "DATABASE_URL must be sqlite (dev) or postgresql+psycopg (production target)."
        )
