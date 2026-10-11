from unittest.mock import patch

import pytest

from config.openai_preflight import OpenAIPreflightError, preflight_openai_realtime
from config.settings import Settings


def test_preflight_rejects_placeholder_key() -> None:
    settings = Settings(openai_api_key="your_openai_api_key", openai_realtime_model="gpt-realtime")
    with pytest.raises(OpenAIPreflightError, match="placeholder"):
        preflight_openai_realtime(settings)


def test_preflight_model_must_be_listed() -> None:
    settings = Settings(openai_api_key="sk-test", openai_realtime_model="gpt-realtime")
    fake_models = [{"id": "gpt-4o"}, {"id": "gpt-realtime-mini"}]
    with patch("config.openai_preflight._fetch_models", return_value=fake_models):
        with pytest.raises(OpenAIPreflightError, match="gpt-realtime"):
            preflight_openai_realtime(settings)
