from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from config.settings import get_settings

_call_context: dict[str, str] = {}


def configure_logging(*, console_mode: bool = False) -> None:
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    # LiveKit legacy console uses Rich Live on stdout; keep app logs off stdout in console.
    log_stream = sys.stderr if console_mode else sys.stdout
    if console_mode and level_name == "INFO":
        level = logging.WARNING

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_call_context,
    ]
    if settings.log_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=log_stream),
    )
    logging.basicConfig(level=level, stream=log_stream)
    if console_mode:
        for logger_name in ("livekit", "livekit.agents", "asyncio", "aiohttp"):
            logging.getLogger(logger_name).setLevel(max(level, logging.WARNING))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_call_context(**kwargs: str) -> None:
    _call_context.update({k: v for k, v in kwargs.items() if v})


def _inject_call_context(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    for key, value in _call_context.items():
        event_dict.setdefault(key, value)
    return event_dict
