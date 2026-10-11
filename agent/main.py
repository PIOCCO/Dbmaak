from __future__ import annotations

import os
import sys

from livekit.agents import AgentServer, JobContext, cli

from agent.receptionist import start_receptionist_session
from config.settings import get_settings
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
    configure_logging()
    try:
        _validate_startup(sys.argv)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    cli.run_app(server)
