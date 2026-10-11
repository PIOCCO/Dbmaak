# AI Voice Receptionist Engine

Modular, production-oriented Python engine for multi-tenant AI phone receptionists. It orchestrates real-time voice conversations with **LiveKit Agents**, **OpenAI Realtime**, and **Twilio/LiveKit SIP** telephony, while keeping business rules, knowledge, tools, and tenant isolation on the server.

This repository is the **core voice engine only** (no frontend, dashboard, or billing).

## Architecture

| Module | Responsibility |
|--------|----------------|
| `agent/` | LiveKit session lifecycle, prompts, routing, receptionist agent |
| `providers/` | Voice model, telephony, and booking backend adapters |
| `knowledge/` | Structured business knowledge loading and retrieval |
| `tools/` | Typed business actions exposed to the model |
| `business/` | Pydantic business profiles and registry |
| `persistence/` | SQLAlchemy models, repositories, Alembic migrations |
| `security/` | Tool authorization, validation, rate limits, idempotency |
| `observability/` | Structured logging and optional OpenTelemetry |
| `config/` | Settings and example business YAML profiles |
| `tests/` | Unit and integration tests (mocked providers by default) |

### Design choices

- **Tenant isolation** uses trusted routing (called number map, dispatch metadata, room prefix `biz-<id>-`), never caller/LLM-provided business IDs.
- **Knowledge** starts as validated YAML → structured documents (RAG-ready interface via `KnowledgeRetriever`).
- **Bookings** use a mock provider backed by PostgreSQL/SQLite with idempotency keys and overlap checks.
- **Provider swaps** stay behind interfaces in `providers/`.

### Compatibility notes (verified against installed packages)

- `livekit-agents` **1.8.6** with `livekit-plugins-openai` **1.8.6**
- Python **3.12+**
- OpenAI Realtime model/voice are configurable via env (`OPENAI_REALTIME_MODEL`, `OPENAI_REALTIME_VOICE`).

## Milestone 1 — Local voice agent (console)

1. **Install**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   cp .env.example .env
   # Fill LIVEKIT_* and OPENAI_API_KEY
   ```

2. **Initialize database** (SQLite default, or Postgres via `DATABASE_URL`)

   ```bash
   alembic upgrade head
   # or for quick local dev:
   python -c "from persistence.db import init_db; init_db()"
   ```

3. **Run the agent worker**

   ```bash
   python agent/main.py download-files   # first-time model/plugin assets
   python agent/main.py dev              # local console / dev room
   ```

   Console mode resolves the tenant from `DEFAULT_BUSINESS_ID` (default: `demo_salon`).

4. **Try business tools without voice**

   ```bash
   python -m pytest -q
   ```

   Tests cover config validation, routing, knowledge retrieval, booking safeguards, authorization, and cross-business isolation.

## Milestone 2 — Inbound phone calls (Twilio + LiveKit SIP)

Telephony stays behind `providers/telephony/`. Production inbound flow:

1. **Twilio** — Programmable Voice / Elastic SIP trunk forwards calls to your LiveKit SIP URI ([LiveKit Twilio guide](https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/)).
2. **LiveKit** — Create an **inbound SIP trunk** and a **dispatch rule** that creates per-caller rooms and dispatches this agent by name (`LIVEKIT_AGENT_NAME`, default `voice-receptionist`).
3. **Tenant routing** — Map each business number using one or more of:
   - `PHONE_NUMBER_BUSINESS_MAP` env JSON
   - `inbound_phone_numbers` on each business YAML profile
   - Dispatch job metadata `{"business_id":"demo_salon"}`
   - Room prefix `biz-demo_salon-<call-id>` for explicit routing
4. **Run the worker** (Docker or bare metal):

   ```bash
   python agent/main.py start
   ```

5. **Human handoff** — Set `HUMAN_HANDOFF_DESTINATION` to a SIP URI or transfer target; `request_human_handoff` calls `JobContext.transfer_sip_participant()` when on a SIP call.

See `.env.example` for all telephony-related variables.

## Business configuration

Example profiles live in `config/businesses/` (`demo_salon.yaml`, `demo_clinic.yaml`).

Add a new tenant by adding a validated YAML file and routing its inbound number(s). The model receives **instructions** separately from **verified facts** (via tools).

## Tools (initial set)

| Tool | Purpose |
|------|---------|
| `get_business_info` | Grounded answers from verified knowledge |
| `get_opening_hours` | Hours and holiday closures |
| `lookup_service` | Service catalog lookup |
| `check_availability` | Mock availability checks |
| `create_booking` | Confirmed bookings only (`confirm=true` + idempotency key) |
| `request_human_handoff` | Escalation / SIP transfer when configured |

## Security & privacy (review before production)

- Secrets only via environment / secret manager (see `.env.example`).
- Full transcripts and caller numbers are **not** logged by default (`LOG_TRANSCRIPTS=false`).
- Call metadata retention is configurable (`CALL_METADATA_RETENTION_DAYS`).
- Tool arguments are validated with Pydantic; unauthorized tools are blocked.
- **Legal/compliance** (recording consent, AI disclosure, data retention) must be reviewed per jurisdiction before taking live traffic.

## Docker

```bash
docker compose up --build
```

The `agent` service expects a populated `.env` with LiveKit and OpenAI credentials.

## Testing

```bash
pytest -q
RUN_LIVEKIT_INTEGRATION=true pytest -m integration   # optional smoke (credentials required)
```

## Assumptions & trade-offs

- Booking integration is **mock-first**; swap `MockBookingProvider` for a real adapter implementing `BookingProvider`.
- Knowledge retrieval is **simple keyword search** for reliability; the store interface is ready for embeddings/RAG later.
- Real-time telephony and voice latency should be validated in staging with real trunks before claiming production readiness.

## Project status

- **Milestone 1**: Implemented — modular engine, tools, knowledge, tests, local LiveKit dev entrypoint.
- **Milestone 2**: Integration path documented and wired (SIP routing + transfer hooks); requires your LiveKit/Twilio project setup and live call testing.
