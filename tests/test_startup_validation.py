from pathlib import Path

import pytest

from config.settings import Settings
from config.startup import ConfigurationError, validate_common, validate_for_worker


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


def test_worker_requires_livekit_and_openai() -> None:
    workspace = Path(__file__).resolve().parents[1]
    settings = Settings(
        business_config_dir=workspace / "config/businesses",
        livekit_url="",
        livekit_api_key="",
        livekit_api_secret="",
        openai_api_key="",
    )
    with pytest.raises(ConfigurationError, match="LIVEKIT_URL"):
        validate_for_worker(settings)
