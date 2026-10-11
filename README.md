# AI Voice Receptionist Engine

Modular, production-oriented Python engine for multi-tenant AI phone receptionists. It orchestrates real-time voice conversations with **LiveKit Agents**, **Azure OpenAI Realtime** (speech-to-speech), and **Twilio/LiveKit SIP** telephony, while keeping business rules, knowledge, tools, and tenant isolation on the server.

Azure setup: [`docs/AZURE.md`](docs/AZURE.md).

This repository is the **core voice engine only** (no frontend, dashboard, or billing).

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module boundaries, tenant isolation, idempotency, and production blockers.

| Module | Responsibility |
|--------|----------------|
| `agent/` | LiveKit session lifecycle, inbound SIP routing, prompts, handoff, receptionist agent |
| `providers/` | Voice model, telephony, and booking backend adapters |
| `knowledge/` | Structured business knowledge loading and retrieval |
| `tools/` | Typed business actions exposed to the model |
| `business/` | Pydantic business profiles, registry, handoff config |
| `persistence/` | SQLAlchemy models, repositories, Alembic migrations |
| `security/` | Tool authorization, validation, rate limits, idempotency |
| `observability/` | Structured lifecycle logs and in-process call metrics |
| `config/` | Settings, business YAML, telephony templates (`config/telephony/`) |
| `docs/` | Detailed Twilio ↔ LiveKit setup (`docs/TELEPHONY.md`) |
| `tests/` | Unit/async tests (mocked providers; no PSTN in CI) |

### Tenant routing (trusted server-side only)

On **real** (non-console) jobs the worker:

1. Waits up to **45s** for a **SIP participant** (`agent/inbound.py`).
2. Reads LiveKit SIP attributes (e.g. `sip.trunkPhoneNumber`) via `LiveKitSipRoutingAdapter`.
3. Resolves `business_id` using, in order (`agent/routing.py`):
   - Dispatch/job metadata `business_id` (if configured server-side)
   - `PHONE_NUMBER_BUSINESS_MAP` env JSON
   - `inbound_phone_numbers` on business YAML (ambiguous duplicates → **fail closed**)
   - Room prefix `biz-<business_id>-`
4. **Console/dev** (`ctx.is_fake_job()`) uses `DEFAULT_BUSINESS_ID` only.

The LLM and caller **cannot** select the tenant.

### Compatibility (checked against installed packages + LiveKit docs)

- `livekit-agents` **1.8.6**, `livekit-plugins-openai` **1.8.6**
- Inbound Twilio path: TwiML `Dial/Sip` → LiveKit inbound trunk + dispatch rule with `roomConfig.agents[].agentName` ([docs](https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/))
- SIP transfer: `JobContext.transfer_sip_participant()` ([cold transfer docs](https://docs.livekit.io/sip/transfer-cold/))

---

## Milestone 1 — Local voice agent (console)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # LIVEKIT_*, AZURE_OPENAI_*
python -c "from persistence.db import init_db; init_db()"
python agent/main.py download-files
python agent/main.py dev
```

Console uses `DEFAULT_BUSINESS_ID` (default `demo_salon`).

---

## Milestone 2 — Inbound telephone calls

**Step-by-step configuration (Twilio + LiveKit CLI, JSON/TwiML templates):** see [`docs/TELEPHONY.md`](docs/TELEPHONY.md).

### Quick reference — dispatch this agent

`config/telephony/livekit-dispatch-voice-receptionist.json`:

```json
"roomConfig": {
  "agents": [{ "agentName": "voice-receptionist" }]
}
```

Create with:

```bash
lk sip inbound create config/telephony/livekit-inbound-trunk.json \
  --auth-user "<user>" --auth-pass "<pass>"
lk sip dispatch create config/telephony/livekit-dispatch-voice-receptionist.json \
  --trunks "<trunk-id>"
```

Worker:

```bash
export LIVEKIT_AGENT_NAME=voice-receptionist
python agent/main.py start
```

Map numbers → businesses:

```bash
export PHONE_NUMBER_BUSINESS_MAP='{"+15550100":"demo_salon","+15550200":"demo_clinic"}'
```

### Human handoff

- Global: `HUMAN_HANDOFF_DESTINATION` (E.164 or `sip:user@host`)
- Per business: `escalation.handoff_destination` in YAML
- Disable: `escalation.handoff_enabled: false`
- Transfer runs only for **SIP** participants; blocked/disabled handoffs are logged and counted (no silent success)

### Call lifecycle observability

Structured logs (no API keys; caller numbers redacted; transcripts off by default):

- `routing_resolved`, `session_start`, `caller_disconnected`, `session_failed`, `handoff_*`

In-process metrics (`observability/metrics.py`): `routing_success`, `routing_failed`, `sip_participant_timeout`, `session_started`, `session_ended`, `handoff_success`, etc. (tags use `business_id` only).

### Mock bookings

- `check_availability` responses are prefixed `[MOCK AVAILABILITY CHECK]`.
- Successful `create_booking` responses include **`[MOCK BOOKING — not a live reservation...]`** and require `confirm=true` after read-back.

---

## Real-call acceptance checklist

Use this after configuring Twilio + LiveKit ( **not** automated in CI):

- [ ] Twilio number rings; TwiML Bin executes `Dial/Sip` to LiveKit with `;transport=tcp`
- [ ] LiveKit inbound trunk auth matches TwiML credentials
- [ ] Dispatch rule attaches agent `voice-receptionist`; worker logs `session_start`
- [ ] SIP participant appears within 45s; logs show `routing_resolved` with expected `business_id`
- [ ] Agent greets with correct **business display name** for that number
- [ ] Tool question (e.g. hours) returns **demo_salon** vs **demo_clinic** content matching the dialed number
- [ ] Unknown number → worker shuts down with `routing_failed` (no wrong tenant)
- [ ] Hang up → `caller_disconnected` / `session_ended` metrics or logs
- [ ] Optional: `request_human_handoff` with destination configured → transfer attempted on SIP call
- [ ] Booking test → model must not claim live reservation without mock notice in tool output

**Status:** This repository has **not** completed a live PSTN test in the cloud agent environment. You must run the checklist on your infrastructure.

---

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| No agent joins | `LIVEKIT_AGENT_NAME`, dispatch `agentName`, worker `start` connected |
| `sip_participant_timeout` | Twilio→LiveKit SIP URI, trunk auth, firewall |
| Wrong business | `PHONE_NUMBER_BUSINESS_MAP` E.164, `sip.trunkPhoneNumber` in LiveKit room |
| `routing_failed` | Unmapped number; add map or `biz-<id>-` room prefix dispatch |
| Handoff fails | Elastic SIP/trunk transfer enabled; `HUMAN_HANDOFF_DESTINATION`; SIP call (not console) |
| Realtime WebSocket closed unexpectedly | [`docs/AZURE.md`](docs/AZURE.md): deployment name, region/SKU, `AZURE_OPENAI_API_VERSION`; preflight (`AZURE_SKIP_PREFLIGHT=1` to skip); `LK_OPENAI_DEBUG=1` |
| `Direct OpenAI is disabled` | Remove `OPENAI_API_KEY`; use `AZURE_OPENAI_*` only |
| Azure auth errors | `AZURE_OPENAI_AUTH_MODE`, key or managed identity RBAC |

More detail: [`docs/TELEPHONY.md`](docs/TELEPHONY.md).

---

## Security & privacy

- Secrets via env / secret manager (`.env.example` placeholders only).
- `LOG_TRANSCRIPTS=false` by default; phone numbers stored redacted in DB.
- Review recording, AI disclosure, and retention laws before production traffic.

---

## Testing

```bash
pytest -q
```

**35 passed**, 1 skipped (optional LiveKit credential smoke). Coverage includes tenant-scoped repositories, idempotent booking retries, startup validation, session finalization, routing, handoff policy, and cross-business isolation.

## Architecture hardening (pre-PSTN)

- `TenantContext` + `TenantScopedBookingRepository` enforce tenant boundaries at persistence/tool layers.
- Durable booking idempotency via `(business_id, idempotency_key)` with payload mismatch detection.
- Bookings persisted with `provider_kind=mock`; tool responses labeled accordingly.
- `CallSessionFinalizer` + idempotent `CallSessionRepository.end`.
- `config/startup.py` validates profiles and worker credentials on `dev` / `start`.

---

## Docker

```bash
docker compose up --build
```

---

## What remains mocked

| Component | Status |
|-----------|--------|
| Booking backend | `MockBookingProvider` + local DB |
| Voice | Azure OpenAI Realtime via LiveKit `RealtimeModel.with_azure` |
| PSTN / Twilio | **You** configure trunks; not exercised in CI |
| RAG | Keyword retrieval only |

Replace mock booking by implementing `providers/booking/base.py` and wiring it in `agent/receptionist.py`.

---

## Credentials & infrastructure you must provide

| Credential / resource | Used for |
|-----------------------|----------|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Worker + rooms |
| `AZURE_OPENAI_*` | Realtime voice (see `docs/AZURE.md`) |
| Twilio number + TwiML Bin | Inbound PSTN |
| LiveKit inbound SIP trunk + dispatch rule | Call → room → agent |
| `PHONE_NUMBER_BUSINESS_MAP` (or per-number dispatch) | Tenant selection |
| Optional `HUMAN_HANDOFF_DESTINATION` | SIP transfer |
| PostgreSQL (recommended prod) or SQLite | Bookings / call metadata |

---

## Commands for your next validation step

```bash
# 1. Automated regression
pytest -q

# 2. Local voice (no phone)
python agent/main.py dev

# 3. Production worker (after Twilio/LiveKit setup)
python agent/main.py start

# 4. Optional credential smoke (does not place a call)
RUN_LIVEKIT_INTEGRATION=true pytest -m integration -q
```

Then place a **real call** to your Twilio number and complete [`docs/INBOUND_CALL_CHECKLIST.md`](docs/INBOUND_CALL_CHECKLIST.md).

**Database:** use `alembic upgrade head` for existing deployments; `init_db()` only creates tables on empty DBs and does not apply incremental migrations.
