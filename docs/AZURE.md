# Azure OpenAI Realtime voice integration

Dbmaak uses **speech-to-speech** via [LiveKit Agents](https://docs.livekit.io/agents/) and the **OpenAI Realtime** WebSocket API exposed by **Azure OpenAI** — not separate STT + chat + TTS, and not direct `api.openai.com`.

## Architecture

```
Caller (SIP/console) → LiveKit room → AgentSession → LiveKit openai.realtime.RealtimeModel (Azure mode)
                                                      → wss://<resource>.openai.azure.com/.../realtime
```

The adapter is `providers/voice/azure_realtime.py`, which calls `openai.realtime.RealtimeModel.with_azure()` from `livekit-plugins-openai` **1.8.6** (same Realtime protocol as OpenAI, routed to your Azure resource).

## Azure resources you need

1. **Azure OpenAI** resource in a [region that supports Realtime](https://learn.microsoft.com/azure/ai-services/openai/concepts/models#audio-models).
2. A **deployment** whose underlying model supports **Realtime audio** (deploy the Realtime-capable model your subscription offers; the deployment **name** is what you put in `AZURE_OPENAI_DEPLOYMENT`, not the raw model SKU string).
3. **Authentication**
   - **Local / CI-style dev:** `AZURE_OPENAI_AUTH_MODE=api_key` and `AZURE_OPENAI_API_KEY`.
   - **Azure production:** `AZURE_OPENAI_AUTH_MODE=managed_identity` on the worker (Container Apps, AKS, VM, etc.) with **Cognitive Services User** (or equivalent) on the OpenAI resource. The agent uses `DefaultAzureCredential` and passes a short-lived Entra token to LiveKit (`entra_token`).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | `https://<name>.openai.azure.com` |
| `AZURE_OPENAI_DEPLOYMENT` | Yes | Your Realtime **deployment name** |
| `AZURE_OPENAI_AUTH_MODE` | Yes | `api_key` or `managed_identity` |
| `AZURE_OPENAI_API_KEY` | If `api_key` | Resource key from Azure portal |
| `AZURE_OPENAI_API_VERSION` | No | Legacy preview APIs only; leave empty for `/openai/v1/realtime` |
| `AZURE_OPENAI_VOICE` | No | Realtime voice (default `marin`) |
| `AZURE_SKIP_PREFLIGHT` | No | Set `1` to skip deployment list check on startup |

**Do not set** `OPENAI_API_KEY` or `OPENAI_BASE_URL`. Startup fails if they are present so the plugin cannot silently use direct OpenAI.

## Local console test

```bash
cp .env.example .env
# Fill LIVEKIT_*, AZURE_OPENAI_*, DATABASE_URL=sqlite+pysqlite:///./receptionist.db

python3 agent/main.py console
```

Preflight tries Azure `GET /openai/deployments` when available. **Foundry** setups often return 404 on that URL (preflight then skips the list and only checks `.env` fields). Skip entirely with `AZURE_SKIP_PREFLIGHT=1` if needed.

**Endpoint:** use **Keys and Endpoint** from the **Azure OpenAI** resource (`https://<name>.openai.azure.com`), not a Foundry project browser URL.

Recommended long term: `lk agent console` (Python `console` subcommand is deprecated by LiveKit).

## Deploying the worker on Azure

1. Build/push the Docker image from this repo (`docker compose` / `Dockerfile`).
2. Run with the same env vars; set `AZURE_OPENAI_AUTH_MODE=managed_identity` and **omit** the API key.
3. Assign a **user-assigned or system-managed identity** with access to the OpenAI resource.
4. Keep LiveKit Cloud (or self-hosted) URL/secrets unchanged; SIP/Twilio flow is unchanged.

## Compatibility and limitations

| Topic | Notes |
|-------|--------|
| LiveKit plugin | `livekit-plugins-openai` 1.8.6; Azure via `RealtimeModel.with_azure` |
| Realtime only | Ordinary Azure **chat completions** deployments cannot replace Realtime voice |
| Entra token refresh | LiveKit Realtime holds one `entra_token` per model instance; long calls may need redeploy/reconnect if the token expires before session end (typical phone calls are fine) |
| Regions / SKUs | Realtime must be enabled for your subscription and region; verify in Azure AI Studio |
| Voices | Must be supported by your Realtime deployment; adjust `AZURE_OPENAI_VOICE` if Azure rejects the voice |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `Direct OpenAI is disabled` | Remove `OPENAI_API_KEY` from `.env` / shell |
| `AZURE_OPENAI_DEPLOYMENT ... not found` | Deployment name in portal; Realtime model deployed |
| WebSocket **404** on both GA and preview URLs | Run `python3 scripts/check_azure_openai.py` from repo root. Usually **deployment name** or **endpoint** does not match Foundry → **Models + endpoints** (same Azure resource). Do not mix GA (`AZURE_OPENAI_API_VERSION` empty) with preview query params. |
| WebSocket **404** on `/openai/v1/realtime?model=...` only | Foundry **GA** Realtime: keep `AZURE_OPENAI_API_VERSION` empty; set `AZURE_OPENAI_DEPLOYMENT` to the exact deployment id (e.g. `gpt-realtime`). |
| WebSocket **404** on preview `/openai/realtime?deployment=...` | Try `AZURE_OPENAI_API_VERSION=2025-04-01-preview` (not 2024-10-01) or migrate deployment to GA `gpt-realtime` in Foundry. |
| WebSocket closed immediately (other) | Key/RBAC, region, Realtime SKU; try another preview version from Azure docs or `LK_OPENAI_DEBUG=1` |
| `managed_identity` errors locally | Use `api_key` locally; MI only where `DefaultAzureCredential` works |

Debug plugin traffic: `LK_OPENAI_DEBUG=1 python3 agent/main.py console`
