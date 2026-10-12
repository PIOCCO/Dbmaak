from pathlib import Path
from unittest.mock import patch

import pytest

from config.settings import Settings
from config.startup import ConfigurationError, validate_common, validate_for_console, validate_for_worker


def test_phone_map_unknown_business_rejected(tmp_path: Path) -> None:
    workspace = Path(__file__).resolve().parents[1]
    cfg = tmp_path / "businesses"
    cfg.mkdir()
    (cfg / "demo_salon.yaml").write_text(
        (workspace / "config/businesses/demo_salon.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    settings = Settings(
        business_config_dir=cfg,
        phone_number_business_map={"+15550100": "missing_biz"},
    )
    with pytest.raises(ConfigurationError, match="unknown business"):
        validate_common(settings)


@patch("config.azure_preflight.preflight_azure_realtime")
def test_console_requires_azure_config(mock_preflight: object) -> None:
    workspace = Path(__file__).resolve().parents[1]
    settings = Settings(
        business_config_dir=workspace / "config/businesses",
        azure_openai_endpoint="",
        azure_openai_deployment="",
    )
    with pytest.raises(ConfigurationError, match="AZURE_OPENAI_ENDPOINT"):
        validate_for_console(settings)


def test_worker_requires_livekit_and_openai() -> None:
    workspace = Path(__file__).resolve().parents[1]
    settings = Settings(
        business_config_dir=workspace / "config/businesses",
        livekit_url="",
        livekit_api_key="",
        livekit_api_secret="",
        azure_openai_endpoint="https://x.openai.azure.com",
        azure_openai_deployment="d",
        azure_openai_api_key="k",
    )
    with pytest.raises(ConfigurationError, match="LIVEKIT_URL"):
        validate_for_worker(settings)
