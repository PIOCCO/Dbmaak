from __future__ import annotations

from typing import Literal

from config.settings import AzureOpenAIAuthMode, Settings

AzureCredentialPair = tuple[str | None, str | None]


class AzureAuthError(RuntimeError):
    pass


def resolve_azure_realtime_credentials(settings: Settings) -> AzureCredentialPair:
    """Return (api_key, entra_token) for LiveKit Azure Realtime — never both set."""
    mode: AzureOpenAIAuthMode = settings.azure_openai_auth_mode

    if mode == "api_key":
        key = settings.azure_openai_api_key.strip()
        if not key or key.startswith("your_"):
            raise AzureAuthError(
                "AZURE_OPENAI_AUTH_MODE=api_key requires AZURE_OPENAI_API_KEY in .env."
            )
        return key, None

    if mode == "managed_identity":
        try:
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise AzureAuthError(
                "managed_identity auth requires the azure-identity package "
                "(install project dependencies)."
            ) from exc

        scope = settings.azure_openai_token_scope.strip()
        credential = DefaultAzureCredential(
            exclude_interactive_browser_credential=True,
        )
        token = credential.get_token(scope)
        if not token.token:
            raise AzureAuthError("DefaultAzureCredential returned an empty token.")
        return None, token.token

    raise AzureAuthError(f"Unsupported AZURE_OPENAI_AUTH_MODE: {mode!r}")


def auth_mode_label(mode: AzureOpenAIAuthMode) -> str:
    return "api-key" if mode == "api_key" else "managed-identity"
