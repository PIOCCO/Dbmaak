# First inbound voice call — acceptance checklist

Use this **after** architecture hardening and **before** treating telephony as production-ready.

**No automated run in CI places a real PSTN call.** You perform this manually.

Platform setup details: [`TELEPHONY.md`](TELEPHONY.md). Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## A. Preconditions (external)

| # | Item | Pass? |
|---|------|-------|
| A1 | LiveKit Cloud project with SIP URI | ☐ |
| A2 | Twilio E.164 number + TwiML Bin → LiveKit SIP (`;transport=tcp`) | ☐ |
| A3 | LiveKit inbound trunk (auth matches TwiML) | ☐ |
| A4 | Dispatch rule with `roomConfig.agents[].agentName` = `voice-receptionist` | ☐ |
| A5 | `PHONE_NUMBER_BUSINESS_MAP` or YAML `inbound_phone_numbers` maps dialed number → business | ☐ |
| A6 | `.env` populated (never commit); worker passes `python agent/main.py dev` validation | ☐ |
| A7 | DB migrated: `alembic upgrade head` (not only `init_db()` on existing DBs) | ☐ |

---

## B. Start worker (Windows PowerShell)

From repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
# Edit .env: LIVEKIT_*, AZURE_OPENAI_*, PHONE_NUMBER_BUSINESS_MAP, DATABASE_URL

alembic upgrade head
python agent/main.py download-files
python agent/main.py start
```

Expected startup:

- No `ConfigurationError` on stderr
- Worker connects to LiveKit (LiveKit CLI / dashboard shows agent registered as `voice-receptionist`)

---

## C. Single test call procedure

1. Dial the Twilio number from a mobile phone.
2. Wait for answer (target: agent speaks within a few seconds after connect).
3. Ask: *“What are your opening hours?”* — answer must match **mapped business** YAML, not the other demo tenant.
4. Ask: *“What services do you offer?”* — tool-grounded catalog; no invented prices.
5. Optional: request booking → agent must read back details, ask confirmation, and any success message must include **`MOCK BOOKING`** (mock mode).
6. Optional: ask for human → only succeeds if `HUMAN_HANDOFF_DESTINATION` / YAML handoff configured and SIP transfer enabled on trunk.
7. Hang up.

---

## D. Success criteria

| Signal | Expected |
|--------|----------|
| LiveKit room | Created with dispatch prefix (e.g. `call-…`) |
| SIP participant | Joins within **45s** (`sip_participant_linked` event / no `sip_participant_timeout`) |
| Log `routing_resolved` | Correct `business_id` for dialed number |
| Log `session_start` | Same `business_id`, `console_mode=false` |
| Agent speech | Correct `display_name` from business YAML |
| Hangup | `caller_disconnected` then single `session_ended` (no duplicate finalize errors) |
| DB `call_sessions` | Row for `call_id`, redacted caller, status `completed` |

---

## E. Failure cases to rehearse

| Scenario | Expected behavior |
|----------|-------------------|
| Unmapped dialed number | `routing_failed` / worker shutdown; **no** wrong tenant |
| Worker stopped | Call fails at carrier/LiveKit (no agent) |
| Wrong `LIVEKIT_AGENT_NAME` | Room created but no agent joins |
| Missing / invalid Azure OpenAI config | Startup `ConfigurationError` or log `session_failed`, call row `failed` |
| Handoff without SIP / destination | Spoken handoff message; log `handoff_skipped` (not silent PSTN transfer) |
| Duplicate booking tool call (same idempotency key) | Same mock booking id returned; no double row |

---

## F. What this does **not** prove

- Live calendar integration (bookings remain `provider_kind=mock` in DB).
- Load, latency SLOs, or international compliance (recording/consent).
- That mock DB booking equals a real appointment.

---

## G. Rollback / safe stop

```powershell
# Stop worker: Ctrl+C in the terminal running `python agent/main.py start`
```

Revoke Twilio → LiveKit routing by detaching TwiML from the number if you need to halt inbound traffic immediately.
