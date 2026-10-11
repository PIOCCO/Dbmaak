from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.azure_validation import AzureConfigError, validate_azure_openai_config, validate_no_direct_openai_env
from config.settings import Settings, clear_settings_cache
from config.startup import ConfigurationError, validate_for_console, validate_for_worker
from providers.voice.factory import build_voice_factory


@pytest.fixture(autouse=True)
def _clear_openai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    clear_settings_cache()


def _azure_settings(**overrides: object) -> Settings:
    workspace = Path(__file__).resolve().parents[1]
    base = {
        "business_config_dir": workspace / "config/businesses",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_deployment": "realtime-demo",
        "azure_openai_auth_mode": "api_key",
        "azure_openai_api_key": "fake-azure-key",
    }
    base.update(overrides)
    return Settings(**base)


def test_rejects_legacy_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-use")
    with pytest.raises(AzureConfigError, match="Direct OpenAI is disabled"):
        validate_no_direct_openai_env()


def test_missing_endpoint_fails_clearly() -> None:
    settings = _azure_settings(azure_openai_endpoint="")
    with pytest.raises(AzureConfigError, match="AZURE_OPENAI_ENDPOINT"):
        validate_azure_openai_config(settings)


def test_missing_deployment_fails_clearly() -> None:
    settings = _azure_settings(azure_openai_deployment="")
    with pytest.raises(AzureConfigError, match="AZURE_OPENAI_DEPLOYMENT"):
        validate_azure_openai_config(settings)


def test_api_key_mode_requires_key() -> None:
    settings = _azure_settings(azure_openai_api_key="")
    with pytest.raises(AzureConfigError, match="AZURE_OPENAI_API_KEY"):
        validate_azure_openai_config(settings)


@patch("azure.identity.DefaultAzureCredential")
def test_managed_identity_uses_entra_not_api_key(mock_cred_cls: MagicMock) -> None:
    token = MagicMock()
    token.token = "entra-access-token"
    mock_cred_cls.return_value.get_token.return_value = token

    settings = _azure_settings(
        azure_openai_auth_mode="managed_identity",
        azure_openai_api_key="",
    )
    validate_azure_openai_config(settings)

    from config.azure_auth import resolve_azure_realtime_credentials

    api_key, entra = resolve_azure_realtime_credentials(settings)
    assert api_key is None
    assert entra == "entra-access-token"


@patch("livekit.plugins.openai.realtime.RealtimeModel.with_azure")
def test_voice_factory_uses_azure_with_azure(mock_with_azure: MagicMock) -> None:
    mock_with_azure.return_value = MagicMock(name="RealtimeModel")
    settings = _azure_settings()
    factory = build_voice_factory(settings)
    model = factory.create_realtime_model()

    assert model is mock_with_azure.return_value
    mock_with_azure.assert_called_once()
    kwargs = mock_with_azure.call_args.kwargs
    assert kwargs["azure_deployment"] == "realtime-demo"
    assert kwargs["azure_endpoint"] == "https://example.openai.azure.com"
    assert kwargs["api_key"] == "fake-azure-key"
    assert kwargs.get("entra_token") is None
    assert kwargs["voice"] == "marin"


def test_download_files_skips_azure_validation() -> None:
    from agent.main import _validate_startup

    _validate_startup(["agent/main.py", "download-files"])


@patch("config.azure_preflight.preflight_azure_realtime")
def test_console_validates_azure_not_openai(mock_preflight: MagicMock) -> None:
    settings = _azure_settings()
    validate_for_console(settings)
    mock_preflight.assert_called_once()


def test_worker_requires_livekit_and_azure() -> None:
    settings = _azure_settings(
        livekit_url="",
        livekit_api_key="",
        livekit_api_secret="",
    )
    with pytest.raises(ConfigurationError, match="LIVEKIT_URL"):
        validate_for_worker(settings)

