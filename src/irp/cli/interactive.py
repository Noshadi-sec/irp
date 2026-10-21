"""Interactive setup prompts and human renderings. Prompts and progress go to stderr."""

from __future__ import annotations

import os
from typing import Any

import typer

from irp.identity import PRODUCT

STATUS_TEXT = {
    "aligned": "registered",
    "stale": "registered (older command)",
    "missing": "not registered",
    "unowned": "has a different 'irp' server",
    "invalid": "configuration unreadable",
}


def _color(text: str, color: str) -> str:
    if os.environ.get("NO_COLOR"):
        return text
    return typer.style(text, fg=color)


def select_clients(states: list[dict[str, Any]]) -> list[str] | None:
    """Multi-select: existing registrations are preselected; newly detected agents are offered, not chosen."""
    typer.echo(f"\n{PRODUCT.display_name} setup. Choose the agents to configure:\n", err=True)
    defaults = []
    for number, state in enumerate(states, start=1):
        preselected = state["registration"] in ("aligned", "stale")
        if preselected:
            defaults.append(str(number))
        detected = "detected" if state["detected"] else "not detected"
        mark = "[x]" if preselected else "[ ]"
        typer.echo(
            f"  {number}. {mark} {state['display_name']:<12} {detected:<13} {STATUS_TEXT[state['registration']]}",
            err=True,
        )
    answer = typer.prompt(
        "\nNumbers separated by commas (Enter keeps the marked ones, 0 for none)",
        default=",".join(defaults) or "0",
        err=True,
    )
    if answer.strip().lower() in ("q", "quit"):
        return None
    chosen: list[str] = []
    for token in answer.replace(" ", "").split(","):
        if token in ("", "0"):
            continue
        if not token.isdigit() or not 1 <= int(token) <= len(states):
            typer.echo(f"Ignoring {token!r}", err=True)
            continue
        chosen.append(states[int(token) - 1]["id"])
    return list(dict.fromkeys(chosen))


def describe_actions(actions: list[dict[str, Any]]) -> None:
    typer.echo("\nPlanned changes:", err=True)
    for action in actions:
        typer.echo(
            f"  - {action['label']}: {action.get('operation', 'remove')} {action['target']}",
            err=True,
        )
        if action.get("backup_path"):
            typer.echo(f"      backup: {action['backup_path']}", err=True)
        if action.get("detail"):
            typer.echo(f"      {action['detail']}", err=True)


def confirm_plan(actions: list[dict[str, Any]]) -> bool:
    describe_actions(actions)
    return typer.confirm("\nApply these changes?", default=False, err=True)


def render_plan(result: dict[str, Any]) -> None:
    status = result["status"]
    if status == "planned":
        if result["planned_actions"]:
            describe_actions(result["planned_actions"])
            typer.echo("\nDry run: nothing was changed. Rerun without --dry-run to apply.")
        else:
            typer.echo("Nothing to change.")
        return
    if status == "cancelled":
        typer.echo("Cancelled; nothing was changed.")
        return
    if status == "needs_confirmation":
        describe_actions(result["planned_actions"])
        typer.echo(f"\n{result['remediation']}")
        return
    if status == "needs_human":
        typer.echo(_color(f"Setup needs you: {result.get('remediation')}", "yellow"))
    for action_id in result.get("applied_actions", []):
        typer.echo(_color(f"  done: {action_id}", "green"))
    doctor = result.get("doctor") or {}
    for check in doctor.get("scope_checks", []):
        mark = _color("ok ", "green") if check["ok"] else _color("FAIL", "red")
        typer.echo(f"  {mark} {check['name']}: {check['detail']}")
    if result.get("restart"):
        typer.echo(f"\nRestart {', '.join(result['restart'])} so it loads {PRODUCT.display_name}.")
    if status == "ready":
        typer.echo(
            _color(
                f'{PRODUCT.display_name} is ready. Ask your agent: "Build arXiv 2501.12345 and check Table 2."',
                "green",
            )
        )


def render_doctor(report: dict[str, Any]) -> None:
    identity = report["identity"]
    typer.echo(
        f"{PRODUCT.display_name} {identity['version']} ({identity['install_method']}), Python at {identity['python']}"
    )
    for title, checks in (
        ("Checks", report["scope_checks"]),
        ("Also seen", report["informational_checks"]),
    ):
        if not checks:
            continue
        typer.echo(f"\n{title}:")
        for check in checks:
            mark = (
                _color("ok  ", "green")
                if check["ok"]
                else _color("FAIL", "red")
                if check["required"]
                else _color("--  ", "yellow")
            )
            typer.echo(f"  {mark} {check['name']}: {check['detail']}")
            if not check["ok"] and check.get("remediation"):
                typer.echo(f"         next: {check['remediation']}")
    verdict = _color("healthy", "green") if report["healthy"] else _color("not healthy", "red")
    typer.echo(f"\n{verdict} ({report['scope']['mode']} scope)")
