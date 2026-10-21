"""uninstall: remove IRP-owned registrations and skill copies. Studies are never touched."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from irp.application.client_config import read_snapshot, remove_registration
from irp.application.clients import supported_clients
from irp.application.registration import home_directory, is_owned
from irp.application.skill_bundle import inspect_skill, remove_skill


def run_uninstall(
    *,
    approved: bool,
    dry_run: bool,
    confirm: Callable[[list[dict[str, Any]]], bool] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    environment = env if env is not None else dict(os.environ)
    home = home_directory(environment)
    clients = supported_clients(home, environment)
    actions: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for client in clients:
        snapshot = read_snapshot(client)
        if snapshot.error is not None:
            return {
                "status": "failed",
                "remediation": f"{snapshot.error} Nothing was removed; repair the file and retry.",
                "planned_actions": [],
            }
        entry = snapshot.entry()
        if entry is None:
            continue
        if is_owned(entry):
            actions.append(
                {
                    "id": f"remove_client:{client.id}",
                    "label": client.display_name,
                    "target": str(client.config_path),
                }
            )
        else:
            kept.append(
                {
                    "target": str(client.config_path),
                    "reason": "registration not written by IRP",
                }
            )
    for root in dict.fromkeys(client.skill_root for client in clients):
        inspection = inspect_skill(root)
        if inspection.state in ("aligned", "stale"):
            actions.append(
                {
                    "id": f"remove_skill:{root}",
                    "label": "skill",
                    "target": str(inspection.destination),
                }
            )
        elif inspection.state in ("unmanaged", "unknown"):
            kept.append({"target": str(inspection.destination), "reason": inspection.detail})
    result: dict[str, Any] = {
        "status": "planned",
        "planned_actions": actions,
        "kept": kept,
        "results": {},
    }
    if dry_run or not actions:
        result["status"] = "planned" if dry_run else "nothing_to_remove"
        return result
    if not approved and confirm is not None:
        approved = confirm(actions)
        if not approved:
            result["status"] = "cancelled"
            return result
    if not approved:
        result["status"] = "needs_confirmation"
        result["remediation"] = "Review the plan, then rerun with --yes."
        return result
    by_id = {client.id: client for client in clients}
    for action in actions:
        kind, target = action["id"].split(":", 1)
        outcome = (
            remove_registration(by_id[target])
            if kind == "remove_client"
            else remove_skill(Path(target))
        )
        result["results"][action["id"]] = outcome
        if outcome["status"] == "failed":
            result["status"] = "failed"
            result["remediation"] = (
                f"{action['label']}: {outcome.get('detail')}. Later removals were not attempted."
            )
            return result
    result["status"] = "removed"
    result["note"] = "Studies, evidence logs and reports are yours and were not touched."
    return result
