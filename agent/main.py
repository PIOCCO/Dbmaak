from __future__ import annotations

import os

from livekit.agents import AgentServer, JobContext, cli

from agent.receptionist import start_receptionist_session
from observability.logging import configure_logging

server = AgentServer()
_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "voice-receptionist")


@server.rtc_session(agent_name=_AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    await start_receptionist_session(ctx)


if __name__ == "__main__":
    configure_logging()
    cli.run_app(server)
