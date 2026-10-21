"""Modal GPU sandboxes for run_remote (experimental).

The Modal SDK runs in a child process so its progress output can never reach
the MCP server's stdout. Real-provider verification of this adapter has not
been recorded yet; treat its results as unverified until a Modal lane runs.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from irp.domain.errors import ErrorCode, IRPError

SUPPORTED_GPUS = ("T4", "L4", "A10G", "L40S", "A100", "A100-80GB", "H100", "H200", "B200")


def modal_status() -> tuple[bool, str]:
    """(usable, detail) without contacting Modal."""
    if importlib.util.find_spec("modal") is None:
        return False, "the modal package is not installed (install irp-agents[modal])"
    has_env_token = bool(os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"))
    has_file_token = (Path.home() / ".modal.toml").is_file()
    if not (has_env_token or has_file_token):
        return (
            False,
            "no Modal token found (run `modal setup` or set MODAL_TOKEN_ID/MODAL_TOKEN_SECRET)",
        )
    return True, "modal package and token found"


def run_in_modal(spec: dict[str, Any], work_dir: Path, timeout_s: float) -> dict[str, Any]:
    """Run the worker with `spec`; returns its result document."""
    usable, detail = modal_status()
    if not usable:
        raise IRPError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            f"Modal is not available: {detail}.",
            remediation="Install `irp-agents[modal]` and authenticate with Modal, or run locally.",
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_path = work_dir / "modal-spec.json"
    result_path = work_dir / "modal-result.json"
    spec_path.write_text(json.dumps({**spec, "result_path": str(result_path)}), encoding="utf-8")
    log_path = work_dir / "modal-client.log"
    with log_path.open("wb") as log:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "irp.providers.compute.modal_worker", str(spec_path)],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_s + 900,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise IRPError(
                ErrorCode.TIMEOUT,
                "The Modal client did not return after the run's time limit plus 15 minutes.",
                remediation=f"Check the Modal dashboard and {log_path}; the sandbox has its own time limit.",
            ) from exc
    if not result_path.is_file():
        raise IRPError(
            ErrorCode.EXECUTION_FAILURE,
            f"The Modal client exited with {completed.returncode} without a result.",
            remediation=f"Read {log_path}.",
        )
    result: dict[str, Any] = json.loads(result_path.read_text(encoding="utf-8"))
    return result
