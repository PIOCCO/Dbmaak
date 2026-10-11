import os

import pytest


@pytest.mark.integration
def test_livekit_console_smoke() -> None:
    if os.getenv("RUN_LIVEKIT_INTEGRATION", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_LIVEKIT_INTEGRATION=true with LiveKit/OpenAI credentials to run.")
    assert os.getenv("LIVEKIT_URL")
    assert os.getenv("OPENAI_API_KEY")
