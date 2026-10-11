# Architecture assessment (Dbmaak voice receptionist)

## Module boundaries and dependency direction

```
agent/          → business/, config/, knowledge/, providers/, persistence/, security/, tools/, observability/
tools/          → business/, knowledge/, providers/, security/ (not agent/ except LiveKit tool wrappers)
providers/      → business/, persistence/, security/ (adapters only)
persistence/    → security.tenant (scope errors only)
business/       → pydantic models + YAML loader (no agent/tools)
security/       → no upward deps
config/         → pydantic-settings
```

LiveKit entrypoint: `agent/main.py` → `agent/receptionist.py` → session + tools.

## Tenant resolution and propagation

1. **Routing** (`agent/inbound.py`, `agent/routing.py`): SIP attributes, env phone map, YAML inbound numbers, room prefix, or console-only `DEFAULT_BUSINESS_ID`.
2. **Authorization artifact**: `TenantContext(business_id, call_id)` created once per session after routing succeeds.
3. **Tools**: `ReceptionistActions` holds `TenantContext`; booking calls assert tenant matches profile.
4. **Persistence**: `TenantScopedBookingRepository` scopes all queries/writes to `tenant.business_id`.
5. **Mock booking provider**: constructed with `(profile, tenant)`; rejects cross-tenant `business_id` arguments.

LLM/caller input never selects tenant.

## Database, transactions, idempotency

- SQLAlchemy models in `persistence/models.py`; Alembic migrations under `persistence/migrations/`.
- Bookings: unique `(business_id, idempotency_key)`; fields `provider_kind`, `duration_minutes`.
- Idempotent retries: same key + same payload returns existing row; mismatched payload → `IdempotencyPayloadMismatchError`.
- Call sessions: `end()` is idempotent (single finalization timestamp).

## Agent lifecycle

- Inbound: wait for SIP participant (45s) on real jobs.
- Routing failure: metric + shutdown (no default tenant on PSTN).
- Session close / failure: `CallSessionFinalizer` ensures one DB finalize.
- Handoff: policy checks before SIP `transfer_sip_participant`.

## Providers

| Interface | Mock | Production path |
|-----------|------|-----------------|
| `BookingProvider` | `MockBookingProvider` | Future live adapter (`BookingProviderKind.LIVE`) |
| Voice | `OpenAIRealtimeVoiceFactory` | OpenAI Realtime via LiveKit plugin |
| Telephony routing | `LiveKitSipRoutingAdapter` | LiveKit SIP attributes |
| Handoff | `agent/handoff.py` | SIP transfer when configured |

## Configuration and secrets

- `config/settings.py` — env-backed settings.
- `config/startup.py` — validates profiles, phone map, worker credentials on CLI `start` / `dev`.
- Secrets not logged; caller numbers redacted in DB.

## Observability

- Structured logs: routing, session, handoff, failures (no transcripts by default).
- `observability/metrics.py` — in-process counters/events tagged by `business_id` only.

## Prioritized findings (addressed in hardening milestone)

| Priority | Finding | Mitigation |
|----------|---------|------------|
| P0 | Repository layer accepted any `business_id` | `TenantScopedBookingRepository` |
| P0 | In-memory idempotency blocked durable retries | DB-first idempotency; retry returns same booking |
| P1 | Call session double-finalize | Idempotent `CallSessionRepository.end` + `CallSessionFinalizer` |
| P1 | Mock bookings not persisted as mock | `provider_kind` column + response labeling |
| P1 | No startup validation | `config/startup.py` |
| P2 | Weak overlap detection | Interval overlap using `duration_minutes` |

## Remaining production blockers

- Live PSTN acceptance not run in CI.
- Live calendar provider not implemented.
- Dispatch metadata trust assumes LiveKit/Twilio server configuration (not caller-controlled).
- PostgreSQL production hardening (RLS, connection pooling, backups) operational — not in app code.
