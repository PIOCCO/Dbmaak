# Twilio → LiveKit SIP → `voice-receptionist` agent

This document matches the **current LiveKit Telephony docs** (Twilio Voice + inbound trunk + dispatch rule with `roomConfig.agents`).

**No real PSTN call is validated in CI.** Use the acceptance checklist in `README.md` after you configure credentials.

## Prerequisites

| Item | Purpose |
|------|---------|
| LiveKit Cloud project | SIP endpoint, trunks, dispatch, agent worker |
| Twilio account + E.164 number | Caller-facing number |
| `lk` CLI | Create inbound trunk and dispatch rule |
| Worker env | `LIVEKIT_*`, `AZURE_OPENAI_*`, `LIVEKIT_AGENT_NAME=voice-receptionist` (see `docs/AZURE.md`) |

## Step 1 — Twilio: TwiML Bin → LiveKit SIP

1. Twilio Console → **Develop → TwiML Bins**.
2. Paste `config/telephony/twiml-inbound.example.xml` and replace placeholders.
3. Assign the bin to your Twilio number (**Phone Numbers → Configure → TwiML Bin**).

Official reference: [Twilio Voice integration](https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/).

> **Note:** TwiML `Dial/Sip` does not support SIP REFER/outbound on the same trunk; use **Elastic SIP Trunking** if you need REFER/cold transfer features beyond LiveKit’s transfer API.

## Step 2 — LiveKit: inbound SIP trunk

1. Copy `config/telephony/livekit-inbound-trunk.example.json` and set your E.164 number.
2. Create the trunk (use the same SIP auth user/password as in TwiML):

```bash
lk sip inbound create config/telephony/livekit-inbound-trunk.json \
  --auth-user "<sip_trunk_username>" \
  --auth-pass "<sip_trunk_password>"
```

Save the returned **trunk ID**.

## Step 3 — LiveKit: dispatch rule → agent

Use `config/telephony/livekit-dispatch-voice-receptionist.json`:

```bash
lk sip dispatch create config/telephony/livekit-dispatch-voice-receptionist.json \
  --trunks "<trunk-id>"
```

Critical fields:

- `roomConfig.agents[].agentName` must equal **`voice-receptionist`** (or your `LIVEKIT_AGENT_NAME`).
- `dispatchRuleIndividual.roomPrefix` (e.g. `call-`) creates one room per caller.

Official reference: [Dispatch rules](https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/).

## Step 4 — Map phone numbers → business profiles

The engine **never** trusts caller speech or LLM output for tenant ID. Configure **server-side** mapping:

**Option A — Environment map (recommended for one worker, many numbers)**

```bash
PHONE_NUMBER_BUSINESS_MAP='{"+15550100":"demo_salon","+15550200":"demo_clinic"}'
```

**Option B — Business YAML `inbound_phone_numbers`**

Already set in `config/businesses/*.yaml`.

**Option C — Per-number dispatch room prefix**

Use `config/telephony/livekit-dispatch-per-business.example.json` per trunk/number so rooms are `biz-demo_salon-*` (parsed by `agent/routing.py`).

**Option D — Dispatch metadata `business_id`**

If your dispatch pipeline injects job metadata JSON with `business_id`, that takes precedence (still server-side).

When a call arrives, the worker waits up to **45s** for a **SIP participant**, reads `sip.trunkPhoneNumber` / related attributes, and loads the matching profile.

## Step 5 — Run the agent worker

```bash
python agent/main.py download-files
python agent/main.py start
```

Ensure the worker is registered with agent name `voice-receptionist` (default in `agent/main.py`).

## Step 6 — Human handoff (optional)

1. Enable cold transfer on your provider trunk ([LiveKit SIP transfer](https://docs.livekit.io/sip/transfer-cold/)).
2. Set global `HUMAN_HANDOFF_DESTINATION` or per-business `escalation.handoff_destination` in YAML.
3. Set `escalation.handoff_enabled: false` to block transfers for a tenant.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Call never reaches agent | TwiML bin attached to number; SIP URI `;transport=tcp`; trunk auth matches TwiML |
| Agent not dispatched | Dispatch rule `agentName` matches `LIVEKIT_AGENT_NAME`; worker `start` logs connected |
| Wrong business profile | `PHONE_NUMBER_BUSINESS_MAP` E.164 formatting; LiveKit SIP attribute `sip.trunkPhoneNumber` in room |
| `routing_failed` in logs | Unknown called number — add mapping or room prefix |
| Handoff silent failure | Not a SIP participant (console mode); missing `HUMAN_HANDOFF_DESTINATION`; transfer disabled on trunk |
| Timeouts | OpenAI/LiveKit credentials; worker egress; `sip_participant_timeout` metric |

## Verify in LiveKit Cloud

Follow LiveKit’s **Testing your telephony setup** checklist: confirm room name prefix, SIP participant attributes, and agent join for a test call.
