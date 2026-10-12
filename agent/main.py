from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, cli

# LiveKit worker reads LIVEKIT_* from os.environ; load .env from repo root first.
load_dotenv()

from config.settings import get_settings


def _sync_env_from_settings() -> None:
    """Expose Azure settings to worker subprocesses; strip legacy OpenAI env vars."""
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENAI_BASE_URL", None)

    settings = get_settings()
    if settings.azure_openai_endpoint.strip():
        os.environ.setdefault("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint.strip())
    if settings.azure_openai_api_key.strip():
        os.environ.setdefault("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key.strip())
    if settings.azure_openai_api_version.strip():
        os.environ.setdefault("AZURE_OPENAI_API_VERSION", settings.azure_openai_api_version.strip())


from agent.receptionist import start_receptionist_session
from config.startup import (
    ConfigurationError,
    validate_database_url,
    validate_for_console,
    validate_for_worker,
)
from observability.logging import configure_logging

server = AgentServer()
_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "voice-receptionist")


@server.rtc_session(agent_name=_AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    await start_receptionist_session(ctx)


def _validate_startup(argv: list[str]) -> None:
    settings = get_settings()
    validate_database_url(settings)
    command = argv[1] if len(argv) > 1 else ""
    if command == "start":
        validate_for_worker(settings)
    elif command in {"dev", "console"}:
        validate_for_console(settings)
    elif command == "download-files":
        return


if __name__ == "__main__":
    _console = len(sys.argv) > 1 and sys.argv[1] == "console"
    configure_logging(console_mode=_console)
    _sync_env_from_settings()
    try:
        _validate_startup(sys.argv)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    cli.run_app(server)
