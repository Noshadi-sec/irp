"""update: upgrade the installation that owns this command, then verify the new version.

uv tool, pipx and virtual-environment installs are upgraded in place with the
exact resolved release. uvx copies and source checkouts are owned by uvx and
git; update tells you the command for those instead of guessing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

import httpx

from irp.application.registration import install_method
from irp.identity import PRODUCT

OUTPUT_LIMIT = 4 * 1024 * 1024


def latest_version() -> str:
    response = httpx.get(
        f"https://pypi.org/pypi/{PRODUCT.package_name}/json",
        timeout=30,
        headers={"User-Agent": PRODUCT.user_agent},
        follow_redirects=True,
    )
    response.raise_for_status()
    version = response.json()["info"]["version"]
    if not isinstance(version, str):
        raise ValueError("PyPI returned no version")
    return version


def version_key(version: str) -> tuple[tuple[int, ...], int, int]:
    """Release numbers, then pre-release rank (a < b < rc < final) and number."""
    match = re.match(r"^(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?", version.strip())
    if not match:
        raise ValueError(f"Unrecognized version {version!r}")
    release = tuple(int(part) for part in match.group(1).split("."))
    release += (0,) * (4 - len(release))
    rank = {"a": 0, "b": 1, "rc": 2}.get(match.group(2) or "", 3)
    return release, rank, int(match.group(3) or 0)


def _newer(candidate: str, current: str) -> bool:
    return version_key(candidate) > version_key(current)


def install_command(method: str, version: str) -> list[str] | None:
    release = f"{PRODUCT.package_name}=={version}"
    if method == "uv_tool":
        return ["uv", "tool", "install", "--force", release]
    if method == "pipx":
        return ["pipx", "install", "--force", release]
    if method in ("venv", "system"):
        return [sys.executable, "-m", "pip", "install", "--upgrade", release]
    return None


def run_update(*, output: str = "human") -> dict[str, Any]:
    method = install_method()
    current = PRODUCT.version
    if method == "uvx":
        return {
            "status": "current",
            "install_method": method,
            "current_version": current,
            "remediation": f"uvx fetches releases itself. Refresh agent registrations with "
            f"`uvx {PRODUCT.latest_package_specifier} setup`.",
        }
    if method == "source":
        return {
            "status": "failed",
            "reason": "unknown-install-method",
            "install_method": method,
            "current_version": current,
            "remediation": "This is a source checkout; update it with git pull.",
        }
    try:
        latest = latest_version()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {
            "status": "failed",
            "reason": "version-check",
            "current_version": current,
            "remediation": f"Could not read the latest release from PyPI ({exc}). Check network access and retry.",
        }
    if not _newer(latest, current):
        return {
            "status": "current",
            "install_method": method,
            "current_version": current,
            "latest_version": latest,
        }
    command = install_command(method, latest)
    assert command is not None
    try:
        completed = subprocess.run(command, capture_output=True, timeout=1800, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "failed",
            "reason": "install",
            "command": command,
            "remediation": str(exc),
        }
    captured = (completed.stdout + completed.stderr)[-OUTPUT_LIMIT:].decode(
        "utf-8", errors="replace"
    )
    if completed.returncode != 0:
        return {
            "status": "failed",
            "reason": "install",
            "command": command,
            "output_tail": captured[-4000:],
            "remediation": "Read the installer output, fix the cause, and rerun the command shown.",
        }
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import {PRODUCT.import_name}; print({PRODUCT.import_name}.__version__)",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    installed = check.stdout.strip()
    if installed != latest:
        return {
            "status": "failed",
            "reason": "verification",
            "installed_version": installed or None,
            "latest_version": latest,
            "remediation": "The new release did not verify; reinstall it with the command shown.",
            "command": command,
        }
    return {
        "status": "updated",
        "install_method": method,
        "previous_version": current,
        "installed_version": installed,
        "command": command,
        "next": f"Run `{PRODUCT.cli_binary} setup` to refresh the skill and any registration pinned to "
        f"{current}, then restart your agents.",
    }
