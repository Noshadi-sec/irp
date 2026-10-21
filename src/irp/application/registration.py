"""The command agents launch, and how to tell whether a registration is IRP's own.

Persistent registrations never point into uv's temporary cache: a uvx run
registers `uvx irp-agents@<exact version> mcp`, pinned to the version that ran
setup. An installed IRP (uv tool, pipx, a virtual environment or a source
checkout) registers its own interpreter with `-m irp mcp`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

from irp.identity import PRODUCT

RegistrationState = Literal["missing", "aligned", "stale", "unowned", "invalid"]


def install_method(prefix: str | None = None, executable: str | None = None) -> str:
    """uvx (ephemeral), uv_tool, pipx, source, venv or system."""
    root = Path(prefix or sys.prefix).as_posix()
    if "/archive-v" in root and "/uv/" in root:
        return "uvx"
    if "/uv/tools/" in root:
        return "uv_tool"
    if "/pipx/venvs/" in root:
        return "pipx"
    package_dir = Path(__file__).resolve().parents[1]
    if (package_dir.parents[1] / "pyproject.toml").is_file() and (
        package_dir.parents[1] / ".agents"
    ).is_dir():
        return "source"
    if sys.prefix != sys.base_prefix:
        return "venv"
    return "system"


def registration_command(method: str | None = None) -> list[str]:
    if (method or install_method()) == "uvx":
        return ["uvx", PRODUCT.registration_package_specifier, "mcp"]
    return [sys.executable, "-m", PRODUCT.import_name, "mcp"]


def is_owned(entry: Any) -> bool:
    """A registration IRP wrote: uvx irp-agents@..., `-m irp`, or a irp executable."""
    if not isinstance(entry, dict):
        return False
    command = entry.get("command")
    args = entry.get("args") or []
    if not isinstance(command, str) or not isinstance(args, list):
        return False
    name = Path(command).name
    if name in ("uvx", "uvx.exe") and args and isinstance(args[0], str):
        return args[0] == PRODUCT.package_name or args[0].startswith(f"{PRODUCT.package_name}@")
    if len(args) >= 2 and args[0] == "-m" and args[1] == PRODUCT.import_name:
        return True
    return name in (PRODUCT.cli_binary, f"{PRODUCT.cli_binary}.exe") and args[:1] == ["mcp"]


def classify(entry: Any, command: list[str]) -> RegistrationState:
    if entry is None:
        return "missing"
    if not isinstance(entry, dict):
        return "invalid"
    if not is_owned(entry):
        return "unowned"
    current = [entry.get("command"), *list(entry.get("args") or [])]
    return "aligned" if current == command else "stale"


def entry_for(command: list[str], previous: Any, *, codex: bool) -> dict[str, Any]:
    """The registration entry; keeps the user's env overrides and Codex timeouts."""
    entry: dict[str, Any] = {"command": command[0], "args": command[1:]}
    if isinstance(previous, dict) and isinstance(previous.get("env"), dict) and previous["env"]:
        entry["env"] = dict(previous["env"])
    if codex:
        entry["startup_timeout_sec"] = _positive(previous, "startup_timeout_sec") or 30
        # Long enough for the CPU-scale runs agents wait on; longer runs use wait=false.
        entry["tool_timeout_sec"] = _positive(previous, "tool_timeout_sec") or 1800
    return entry


def _positive(previous: Any, key: str) -> int | None:
    if isinstance(previous, dict):
        value = previous.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return None


def home_directory(env: dict[str, str] | None = None) -> Path:
    environment = env if env is not None else dict(os.environ)
    home = environment.get("HOME") or environment.get("USERPROFILE")
    return Path(home) if home else Path.home()
