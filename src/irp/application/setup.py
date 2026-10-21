"""setup: register IRP with agents and install the skill, only after showing the plan.

Discovery is read-only. Detection gives context, not permission: newly detected
agents are offered but not selected. Without an explicit scope, --yes covers
only existing IRP registrations. Nothing is written until the plan is
approved, and setup never installs unrelated software (uv, Docker, git, Python).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from irp.application.client_config import apply_registration, inspect_registration
from irp.application.clients import (
    SUPPORTED_CLIENT_IDS,
    AgentClient,
    shared_skill_root,
    supported_clients,
)
from irp.application.doctor import run_doctor
from irp.application.registration import home_directory, registration_command
from irp.application.skill_bundle import inspect_skill, install_skill
from irp.identity import PRODUCT

Selector = Callable[[list[dict[str, Any]]], list[str] | None]
Confirmer = Callable[[list[dict[str, Any]]], bool]


@dataclass
class SetupOptions:
    clients: list[str] = field(default_factory=list)
    all_detected: bool = False
    install_skill: bool | None = None
    dry_run: bool = False
    approved: bool = False


def _client_state(client: AgentClient, command: list[str]) -> dict[str, Any]:
    inspection = inspect_registration(client, command)
    return {
        "id": client.id,
        "display_name": client.display_name,
        "detected": client.detected,
        "registration": inspection.state,
        "config_path": str(client.config_path),
        "needs_change": inspection.operation is not None,
        "blocker": inspection.blocker,
    }


def run_setup(
    options: SetupOptions,
    *,
    select: Selector | None = None,
    confirm: Confirmer | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    environment = env if env is not None else dict(os.environ)
    home = home_directory(environment)
    command = registration_command()
    clients = {client.id: client for client in supported_clients(home, environment)}
    states = [_client_state(client, command) for client in clients.values()]
    result: dict[str, Any] = {
        "status": "planned",
        "registration_command": command,
        "client_states": states,
        "planned_actions": [],
        "applied_actions": [],
        "results": {},
    }

    unknown = [cid for cid in options.clients if cid not in clients]
    if unknown:
        return _needs_human(
            result,
            f"Unsupported client {unknown[0]!r}; supported: {', '.join(SUPPORTED_CLIENT_IDS)}.",
        )
    if options.clients:
        selected = list(dict.fromkeys(options.clients))
    elif options.all_detected:
        selected = [s["id"] for s in states if s["detected"]]
    elif select is not None:
        chosen = select(states)
        if chosen is None:
            result["status"] = "cancelled"
            return result
        selected = chosen
    else:
        # --yes alone refreshes only what IRP already registered.
        selected = [s["id"] for s in states if s["registration"] in ("aligned", "stale")]
    install = options.install_skill if options.install_skill is not None else bool(selected)
    result["selected_clients"] = selected

    actions: list[dict[str, Any]] = []
    for client_id in selected:
        client = clients[client_id]
        inspection = inspect_registration(client, command)
        if inspection.blocker:
            return _needs_human(result, f"{client.display_name}: {inspection.blocker}")
        if inspection.operation is None:
            continue
        actions.append(
            {
                "id": f"configure_client:{client.id}",
                "kind": "configure_client",
                "label": client.display_name,
                "target": str(client.config_path),
                "operation": inspection.operation,
                "backup_path": str(inspection.backup_path) if inspection.backup_path else None,
                "detail": f"Add the {PRODUCT.display_name} MCP registration; keep every other setting. "
                f"Command: {' '.join(command)}." + (f" {client.note}" if client.note else ""),
            }
        )
    skill_roots = list(dict.fromkeys(str(clients[c].skill_root) for c in selected)) or (
        [str(shared_skill_root(home))] if options.install_skill else []
    )
    if install:
        for root in skill_roots:
            skill_check = inspect_skill(Path(root))
            if skill_check.state in ("unmanaged", "unknown"):
                return _needs_human(
                    result,
                    f"{skill_check.destination} exists and is not managed by IRP ({skill_check.detail}). "
                    "Move it, or rerun with --no-skill.",
                )
            if skill_check.state != "aligned":
                actions.append(
                    {
                        "id": f"install_skill:{root}",
                        "kind": "install_skill",
                        "label": f"{PRODUCT.skill_name} skill",
                        "target": str(skill_check.destination),
                        "operation": "update" if skill_check.state == "stale" else "create",
                        "backup_path": None,
                        "detail": "Install the bundled workflow and hard rules with an ownership manifest.",
                    }
                )
    result["planned_actions"] = actions
    if options.dry_run:
        return result
    if not actions:
        result["status"] = "ready"
        result["doctor"] = _scoped_doctor(selected, install, environment)
        return result
    approved = options.approved
    if not approved and confirm is not None:
        approved = confirm(actions)
        if not approved:
            result["status"] = "cancelled"
            return result
    if not approved:
        result["status"] = "needs_confirmation"
        result["remediation"] = (
            "Review the plan, then rerun with --yes and the same scope, e.g. "
            f"`{PRODUCT.cli_binary} setup --client claude_code --yes`."
        )
        return result

    for action in actions:
        if action["kind"] == "configure_client":
            client = clients[action["id"].split(":", 1)[1]]
            outcome = apply_registration(client, command)
        else:
            outcome = install_skill(Path(action["id"].split(":", 1)[1]))
        result["results"][action["id"]] = outcome
        if outcome["status"] == "failed":
            return _needs_human(result, f"{action['label']}: {outcome.get('detail')}")
        result["applied_actions"].append(action["id"])
    doctor = _scoped_doctor(selected, install, environment)
    result["doctor"] = doctor
    result["status"] = "ready" if doctor["healthy"] else "needs_human"
    configured = [
        clients[c].display_name
        for c in selected
        if f"configure_client:{c}" in result["applied_actions"]
    ]
    if configured:
        result["restart"] = configured
    return result


def _scoped_doctor(selected: list[str], skill: bool, environment: dict[str, str]) -> dict[str, Any]:
    report = run_doctor(clients=selected, skill=skill, env=environment)
    return {
        "healthy": report["healthy"],
        "scope_checks": [
            {k: c[k] for k in ("name", "ok", "detail", "remediation")}
            for c in report["scope_checks"]
        ],
    }


def _needs_human(result: dict[str, Any], remediation: str) -> dict[str, Any]:
    result["status"] = "needs_human"
    result["remediation"] = remediation
    return result
