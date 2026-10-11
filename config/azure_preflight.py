from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode

from config.azure_auth import resolve_azure_realtime_credentials
from config.settings import Settings


class AzurePreflightError(RuntimeError):
    pass


def preflight_enabled() -> bool:
    return os.getenv("AZURE_SKIP_PREFLIGHT", "").lower() not in {"1", "true", "yes"}


def _list_deployments(settings: Settings, api_key: str | None, entra_token: str | None) -> list[str]:
    api_version = settings.azure_openai_api_version.strip() or "2024-06-01"
    base = settings.azure_openai_endpoint.rstrip("/")
    query = urlencode({"api-version": api_version})
    url = f"{base}/openai/deployments?{query}"
    headers = {"Content-Type": "application/json"}
    if entra_token:
        headers["Authorization"] = f"Bearer {entra_token}"
    if api_key:
        headers["api-key"] = api_key

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise AzurePreflightError(
                "Azure OpenAI credentials were rejected (HTTP "
                f"{exc.code}). Check AZURE_OPENAI_API_KEY or managed identity RBAC."
            ) from exc
        body = exc.read().decode("utf-8", errors="replace")
        raise AzurePreflightError(
            f"Azure deployments API returned HTTP {exc.code}: {body[:400]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AzurePreflightError(
            f"Could not reach Azure OpenAI endpoint ({exc.reason}). Check AZURE_OPENAI_ENDPOINT."
        ) from exc

    data = payload.get("data")
    if not isinstance(data, list):
        raise AzurePreflightError("Unexpected response from Azure /openai/deployments.")
    names: list[str] = []
    for entry in data:
        if isinstance(entry, dict) and entry.get("id"):
            names.append(str(entry["id"]))
    return names


def preflight_azure_realtime(settings: Settings) -> None:
    api_key, entra_token = resolve_azure_realtime_credentials(settings)
    deployment = settings.azure_openai_deployment.strip()
    names = _list_deployments(settings, api_key, entra_token)
    if deployment not in names:
        hint = ", ".join(names[:8]) if names else "(none returned)"
        raise AzurePreflightError(
            f"AZURE_OPENAI_DEPLOYMENT={deployment!r} was not found on this resource. "
            f"Deployments seen: {hint}"
        )
