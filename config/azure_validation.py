from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from config.azure_auth import AzureAuthError, resolve_azure_realtime_credentials
from config.settings import Settings

_ENDPOINT_RE = re.compile(r"^https://[a-z0-9-]+\.(openai|cognitiveservices)\.azure\.com/?$", re.I)


class AzureConfigError(RuntimeError):
    pass


def validate_no_direct_openai_env() -> None:
    """Reject legacy direct-OpenAI env vars so the LiveKit plugin cannot silently use them."""
    legacy = []
    if os.getenv("OPENAI_API_KEY", "").strip():
        legacy.append("OPENAI_API_KEY")
    if os.getenv("OPENAI_BASE_URL", "").strip():
        legacy.append("OPENAI_BASE_URL")
    if legacy:
        raise AzureConfigError(
            "Direct OpenAI is disabled. Remove "
            + ", ".join(legacy)
            + " and configure AZURE_OPENAI_* instead (see docs/AZURE.md)."
        )


def validate_azure_openai_config(settings: Settings) -> None:
    validate_no_direct_openai_env()

    endpoint = settings.azure_openai_endpoint.strip()
    if not endpoint:
        raise AzureConfigError(
            "Missing AZURE_OPENAI_ENDPOINT (e.g. https://your-resource.openai.azure.com)."
        )
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise AzureConfigError("AZURE_OPENAI_ENDPOINT must be an https URL to your Azure OpenAI resource.")
    normalized = f"{parsed.scheme}://{parsed.netloc}"
    if not _ENDPOINT_RE.match(normalized.rstrip("/") + "/"):
        raise AzureConfigError(
            "AZURE_OPENAI_ENDPOINT should look like "
            "https://<resource>.openai.azure.com or https://<resource>.cognitiveservices.azure.com."
        )

    deployment = settings.azure_openai_deployment.strip()
    if not deployment:
        raise AzureConfigError(
            "Missing AZURE_OPENAI_DEPLOYMENT — use your Azure deployment name for the Realtime model."
        )

    try:
        resolve_azure_realtime_credentials(settings)
    except AzureAuthError as exc:
        raise AzureConfigError(str(exc)) from exc
