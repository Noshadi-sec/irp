"""Logging goes to stderr only, so stdout carries protocol messages and command results.

IRP_LOG_LEVEL selects debug, info, warning, error or silent. MCP defaults to
info; one-shot CLI logging is opt-in.
"""

from __future__ import annotations

import logging
import os
import sys

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "silent": logging.CRITICAL + 10,
}


def parse_level(value: str | None, default_level: str) -> int:
    name = (value or default_level).strip().lower()
    if name not in LEVELS:
        raise ValueError(f"IRP_LOG_LEVEL must be one of {', '.join(LEVELS)}; got {value!r}.")
    return LEVELS[name]


def configure_logging(default_level: str = "silent") -> None:
    level = parse_level(os.environ.get("IRP_LOG_LEVEL"), default_level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("irp")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
