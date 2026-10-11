from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from config.settings import Settings


class OpenAIPreflightError(RuntimeError):
    pass


def _fetch_models(api_key: str, *, timeout: float = 15.0) -> list[dict]:
    request = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key.strip()}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise OpenAIPreflightError(
                "OPENAI_API_KEY was rejected by OpenAI (HTTP 401). "
                "Create a new key at https://platform.openai.com/api-keys "
                "and ensure billing is enabled for Realtime."
            ) from exc
        raise OpenAIPreflightError(
            f"OpenAI models API returned HTTP {exc.code}: {body[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OpenAIPreflightError(
            f"Could not reach OpenAI API ({exc.reason}). Check network / proxy."
        ) from exc

    data = payload.get("data")
    if not isinstance(data, list):
        raise OpenAIPreflightError("Unexpected response from OpenAI /v1/models.")
    return data


def preflight_openai_realtime(settings: Settings) -> None:
    """Verify API key and that the configured Realtime model id is listed."""
    api_key = settings.openai_api_key.strip()
    if not api_key or api_key.startswith("your_"):
        raise OpenAIPreflightError(
            "OPENAI_API_KEY is missing or still a placeholder in .env."
        )

    model = settings.openai_realtime_model.strip()
    models = _fetch_models(api_key)
    ids = {str(entry.get("id", "")) for entry in models if isinstance(entry, dict)}
    if model not in ids:
        realtime_like = sorted(m for m in ids if "realtime" in m.lower())
        hint = (
            f" Set OPENAI_REALTIME_MODEL to one of: {', '.join(realtime_like[:8])}"
            if realtime_like
            else " Check https://platform.openai.com/docs/models for Realtime model ids."
        )
        raise OpenAIPreflightError(
            f"OPENAI_REALTIME_MODEL={model!r} is not available for this API key.{hint}"
        )


def preflight_enabled() -> bool:
    return os.getenv("OPENAI_SKIP_PREFLIGHT", "").lower() not in {"1", "true", "yes"}
