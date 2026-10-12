# Local voice console (testing)

## Recommended

```bash
# From repo root, real terminal (not all IDE "Run" panels)
cd ~/Azelos/Dbmaak
source .venv/bin/activate
LOG_LEVEL=WARNING python3 agent/main.py console
```

Long term, use the **LiveKit CLI** (stable TUI, less log fighting):

```bash
lk agent console
```

See [LiveKit CLI setup](https://docs.livekit.io/reference/developer-tools/livekit-cli/#setup).

## If the session closes by itself (~1 second)

Common causes:

1. **Not a real TTY** — IDE run buttons often have no proper stdin. Check:
   ```bash
   test -t 1 && echo "TTY ok" || echo "NOT a TTY — open gnome-terminal / konsole / ssh -t"
   ```
2. **Legacy Python console** — `python3 agent/main.py console` uses a deprecated Rich UI that can race with the worker thread. Prefer **`lk agent console`**.
3. **Microphone** — list devices:
   ```bash
   python3 agent/main.py console --list-devices
   ```
   Install PortAudio on Linux: `sudo apt install libportaudio2 portaudio19-dev`
4. **Azure still failing** — if logs show WebSocket 404/401, fix `.env` first ([AZURE.md](./AZURE.md)).

Capture a full trace:

```bash
LOG_LEVEL=DEBUG LK_OPENAI_DEBUG=1 python3 agent/main.py console 2>&1 | tee /tmp/dbmaak-console.log
```

## How to use audio mode

- **Speak** into the mic; you do not type commands in audio mode.
- **Ctrl+T** — toggle text ↔ audio (text mode uses a special prompt; typing may not echo normally).
- **Ctrl+C** — quit.

## `.env` minimum for console

Same as voice worker: `LIVEKIT_*`, `AZURE_OPENAI_*`, `DATABASE_URL=sqlite+pysqlite:///./receptionist.db`, `DEFAULT_BUSINESS_ID=demo_salon`.
