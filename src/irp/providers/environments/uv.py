"""uv virtual environments: fast, pinned, and they give a lock file.

IRP reuses an existing uv; it never installs or upgrades uv itself. A
virtual environment is not a sandbox: code in it runs with your permissions.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from irp.domain.errors import ErrorCode, IRPError

INSTALL_TIMEOUT_S = 3600


@dataclass(frozen=True)
class UvEnvironment:
    venv: Path
    python: Path
    python_version: str
    uv_version: str
    lock_text: str


def uv_executable() -> str | None:
    configured = os.environ.get("IRP_UV")
    if configured:
        return configured if Path(configured).is_file() else None
    return shutil.which("uv")


def uv_version(uv: str) -> str:
    result = subprocess.run(
        [uv, "--version"], capture_output=True, text=True, timeout=30, check=False
    )
    return result.stdout.strip() or result.stderr.strip()


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def venv_bin(venv: Path) -> Path:
    return venv / ("Scripts" if sys.platform == "win32" else "bin")


def _run(
    command: list[str], cwd: Path, timeout: int, what: str
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise IRPError(
            ErrorCode.TIMEOUT,
            f"{what} did not finish within {timeout} s.",
            remediation="Check network access to the package index, then retry.",
        ) from exc
    if result.returncode != 0:
        raise IRPError(
            ErrorCode.EXECUTION_FAILURE,
            f"{what} failed with exit code {result.returncode}.",
            remediation="Read the error output. Pin or fix the requirement that failed; if the "
            "paper's dependency cannot be installed, record a guess or report could not run.",
            details={
                "command": command,
                "stderr": result.stderr[-4000:],
                "stdout": result.stdout[-2000:],
            },
        )
    return result


def create_uv_environment(
    *,
    venv: Path,
    python: str,
    code_dir: Path,
    requirements: Path | None,
    packages: list[str],
) -> UvEnvironment:
    uv = uv_executable()
    if uv is None:
        raise IRPError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "uv is not on PATH.",
            remediation="Install uv (https://docs.astral.sh/uv/getting-started/installation/) and "
            "retry, or set IRP_UV to its path. IRP does not install uv for you.",
        )
    if venv.exists():
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"The environment directory {venv} already exists.",
            remediation="Choose a new environment name; environments are never rebuilt in place, "
            "so earlier runs keep the lock they used.",
        )
    _run(
        [uv, "venv", str(venv), "--python", python, "--no-project"],
        code_dir,
        600,
        "Creating the uv environment",
    )
    interpreter = venv_python(venv)
    if requirements is not None:
        _run(
            [uv, "pip", "install", "--python", str(interpreter), "-r", str(requirements)],
            code_dir,
            INSTALL_TIMEOUT_S,
            "Installing requirements",
        )
    if packages:
        _run(
            [uv, "pip", "install", "--python", str(interpreter), *packages],
            code_dir,
            INSTALL_TIMEOUT_S,
            "Installing packages",
        )
    freeze = _run(
        [uv, "pip", "freeze", "--python", str(interpreter)],
        code_dir,
        300,
        "Freezing the environment",
    )
    version = subprocess.run(
        [str(interpreter), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    ).stdout.strip()
    return UvEnvironment(
        venv=venv,
        python=interpreter,
        python_version=version,
        uv_version=uv_version(uv),
        lock_text=freeze.stdout,
    )
