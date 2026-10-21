"""doctor: read-only readiness checks. It never installs, starts or changes anything.

Without scope options it audits everything it can see; `healthy` can be false
while your chosen workflow still works. With --client or --skill, only the
selected checks decide `healthy`, and the rest are informational.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from irp.application.client_config import inspect_registration
from irp.application.clients import SUPPORTED_CLIENT_IDS, supported_clients
from irp.application.registration import home_directory, install_method, registration_command
from irp.application.skill_bundle import bundled_skill_dir, inspect_skill, skill_version
from irp.identity import PRODUCT
from irp.logging_setup import parse_level
from irp.providers.compute.local import gpu_names
from irp.providers.compute.modal import modal_status
from irp.providers.environments.docker import docker_status
from irp.providers.environments.uv import uv_executable, uv_version

LOW_DISK_BYTES = 10 * 1024**3


def _check(
    name: str,
    ok: bool,
    detail: str,
    *,
    classification: str = "healthy",
    remediation: str | None = None,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "classification": "healthy" if ok else classification,
        "detail": detail,
        "remediation": None if ok else remediation,
        "required": required,
    }


def _version_of(executable: str, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            [executable, *args], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (
        (result.stdout or result.stderr).strip().splitlines()[0]
        if (result.stdout or result.stderr)
        else None
    )


def host_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    version = ".".join(str(part) for part in sys.version_info[:3])
    checks.append(
        _check(
            "python",
            sys.version_info >= (3, 11),
            f"Python {version} at {sys.executable}",
            classification="unsupported_host",
            remediation="IRP needs Python 3.11 or newer.",
        )
    )
    try:
        parse_level(os.environ.get("IRP_LOG_LEVEL"), "info")
        checks.append(_check("log_level", True, os.environ.get("IRP_LOG_LEVEL") or "default"))
    except ValueError as exc:
        checks.append(
            _check(
                "log_level",
                False,
                str(exc),
                classification="config_drift",
                remediation="Unset or fix IRP_LOG_LEVEL.",
            )
        )
    uv = uv_executable()
    checks.append(
        _check(
            "uv",
            uv is not None,
            f"{uv_version(uv)} at {uv}" if uv else "uv is not on PATH",
            classification="missing_dependency",
            remediation="Install uv (https://docs.astral.sh/uv/) for create_env backend='uv'. IRP does not install it.",
        )
    )
    git = shutil.which("git")
    checks.append(
        _check(
            "git",
            git is not None,
            (_version_of(git, ["--version"]) or "git") if git else "git is not on PATH",
            classification="missing_dependency",
            remediation="Install git; runs are tied to code commits.",
        )
    )
    docker_ok, docker_detail = docker_status()
    checks.append(
        _check(
            "docker",
            docker_ok,
            f"Docker server {docker_detail}" if docker_ok else docker_detail,
            classification="missing_dependency",
            remediation="Optional: install and start Docker to isolate runs (create_env backend='docker').",
            required=False,
        )
    )
    gpus = gpu_names()
    gpu_detail = ", ".join(gpus) if gpus else "no NVIDIA GPU visible (nvidia-smi absent or empty)"
    if not gpus and sys.platform == "darwin":
        gpu_detail += "; Apple GPUs are reachable from PyTorch (MPS) but are not CUDA"
    checks.append(
        _check(
            "gpu",
            bool(gpus),
            gpu_detail,
            classification="missing_dependency",
            required=False,
            remediation="Optional: GPU papers can use run_remote with an approved budget.",
        )
    )
    usage = shutil.disk_usage(Path.home())
    checks.append(
        _check(
            "disk",
            usage.free >= LOW_DISK_BYTES,
            f"{usage.free / 1024**3:.1f} GiB free in {Path.home()}",
            classification="runtime_failure",
            remediation="Free some space; environments and datasets need several GiB.",
            required=False,
        )
    )
    for module, purpose, required in (
        ("pypdf", "PDF text", True),
        ("pypdfium2", "page images", True),
        ("docling", "structured PDF parsing (optional extra irp-agents[docling])", False),
    ):
        present = importlib.util.find_spec(module) is not None
        checks.append(
            _check(
                f"parser:{module}",
                present,
                f"{module} {'available' if present else 'not installed'} ({purpose})",
                classification="missing_dependency",
                remediation=f"Reinstall {PRODUCT.package_name}"
                if required
                else f"Optional: install {PRODUCT.package_name}[docling].",
                required=required,
            )
        )
    modal_ok, modal_detail = modal_status()
    checks.append(
        _check(
            "compute:modal",
            modal_ok,
            modal_detail,
            classification="missing_dependency",
            required=False,
            remediation="Optional: install irp-agents[modal] and run `modal setup` for run_remote.",
        )
    )
    return checks


def run_doctor(
    *, clients: list[str], skill: bool, env: dict[str, str] | None = None
) -> dict[str, Any]:
    environment = env if env is not None else dict(os.environ)
    home = home_directory(environment)
    explicit = bool(clients) or skill
    unknown = [c for c in clients if c not in SUPPORTED_CLIENT_IDS]
    command = registration_command()
    checks = host_checks()
    registrations = []
    skill_roots: dict[str, tuple[Path, bool]] = {}
    for client in supported_clients(home, environment):
        inspection = inspect_registration(client, command)
        selected = client.id in clients
        relevant = selected or (not explicit and client.detected)
        state = inspection.state
        ok = state == "aligned" and inspection.operation is None
        detail = f"{client.display_name}: {state} in {client.config_path}"
        remediation = None
        if state in ("missing", "stale") or (
            state == "aligned" and inspection.operation is not None
        ):
            remediation = f"Run `{PRODUCT.cli_binary} setup --client {client.id} --dry-run`, review it, then apply."
        elif inspection.blocker:
            remediation = inspection.blocker
        registrations.append(
            {
                "client": client.id,
                "detected": client.detected,
                "state": state,
                "config_path": str(client.config_path),
                "registered_command": inspection.entry.get("command")
                if isinstance(inspection.entry, dict)
                else None,
            }
        )
        if relevant:
            checks.append(
                _check(
                    f"client:{client.id}",
                    ok,
                    detail,
                    classification="config_drift" if state != "missing" else "missing_dependency",
                    remediation=remediation,
                    required=selected or (not explicit and state not in ("missing",)),
                )
            )
        # A selected client's skill copy must exist; elsewhere only installed copies are judged.
        if selected or not clients:
            previous = skill_roots.get(str(client.skill_root), (client.skill_root, False))
            skill_roots[str(client.skill_root)] = (client.skill_root, previous[1] or selected)
    for name in unknown:
        checks.append(
            _check(
                f"client:{name}",
                False,
                f"{name} is not a supported client",
                classification="config_drift",
                remediation=f"Supported: {', '.join(SUPPORTED_CLIENT_IDS)}.",
            )
        )
    expected_version = skill_version(bundled_skill_dir() / "SKILL.md")
    skill_states = []
    installed_copies = 0
    for root, must_exist in skill_roots.values():
        skill_check = inspect_skill(root)
        skill_states.append(skill_check.to_dict())
        installed = skill_check.state != "missing"
        installed_copies += int(installed)
        if not installed and not (skill and must_exist):
            continue
        checks.append(
            _check(
                f"skill:{root}",
                skill_check.state == "aligned",
                f"{PRODUCT.skill_name} {skill_check.state} at {skill_check.destination}",
                classification="config_drift",
                remediation=f"Run `{PRODUCT.cli_binary} setup` to install or refresh the skill."
                if skill_check.state in ("missing", "stale")
                else f"{skill_check.destination} is not managed by IRP ({skill_check.detail}); "
                "leave it or remove it yourself.",
            )
        )
    if skill and not clients and installed_copies == 0:
        checks.append(
            _check(
                "skill:installed",
                False,
                f"no installed copy of {PRODUCT.skill_name}",
                classification="missing_dependency",
                remediation=f"Run `{PRODUCT.cli_binary} setup` to install the skill.",
            )
        )
    if explicit:
        scope_names = {f"client:{c}" for c in clients} | (
            {c["name"] for c in checks if c["name"].startswith("skill:")} if skill else set()
        )
        scope_names |= {"python", "log_level"}
        scope_checks = [c for c in checks if c["name"] in scope_names]
    else:
        scope_checks = [c for c in checks if c["required"]]
    informational = [c for c in checks if c not in scope_checks]
    return {
        "healthy": all(c["ok"] for c in scope_checks),
        "environment_healthy": all(c["ok"] for c in checks if c["required"]),
        "scope": {"mode": "explicit" if explicit else "audit", "clients": clients, "skill": skill},
        "scope_checks": scope_checks,
        "informational_checks": informational,
        "identity": {
            "version": PRODUCT.version,
            "install_method": install_method(),
            "python": sys.executable,
            "registration_command": command,
            "expected_skill_version": expected_version,
            "skills": skill_states,
            "registrations": registrations,
            "live_server": "unknown: doctor reads files; restart the agent to load a changed registration",
        },
    }
