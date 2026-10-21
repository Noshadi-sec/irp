"""CLI adapter: the same tools, for you, plus setup, doctor, update, uninstall and budget.

Every tool command builds the same contract input the MCP server receives and
calls the same core, so the CLI and the agent produce identical evidence.
"""

from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from irp.application.context import OperationContext
from irp.application.operations import execute
from irp.cli.output import emit, emit_error
from irp.contracts.catalog import BY_NAME, CATALOG
from irp.domain.errors import ErrorCode, IRPError
from irp.identity import PRODUCT

app = typer.Typer(
    name=PRODUCT.cli_binary,
    help=f"{PRODUCT.display_name}: {PRODUCT.promise}\n\nTurn a research paper into working code and prove, "
    "claim by claim, how close it gets. Your agent is the brain; IRP acts and keeps the receipts.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)
claim_app = typer.Typer(help="Record and list the paper's claims.", no_args_is_help=True)
guess_app = typer.Typer(help="Record details the paper left out.", no_args_is_help=True)
note_app = typer.Typer(
    help="Record limitations, deviations and author contacts.", no_args_is_help=True
)
env_app = typer.Typer(help="Build pinned environments.", no_args_is_help=True)
budget_app = typer.Typer(
    help="Paid compute budget and prices (a person sets these; agents cannot).",
    no_args_is_help=True,
)
app.add_typer(claim_app, name="claim")
app.add_typer(guess_app, name="guess")
app.add_typer(note_app, name="note")
app.add_typer(env_app, name="env")
app.add_typer(budget_app, name="budget")

StudyOption = Annotated[
    Path,
    typer.Option(
        "--study",
        "-s",
        help="Study directory (default: the current directory).",
        show_default=False,
    ),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print JSON instead of text.")]


def _version(value: bool) -> None:
    if value:
        typer.echo(PRODUCT.version)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Print the version and exit."
        ),
    ] = False,
) -> None:
    """Build any paper. Prove every claim."""


def _study(path: Path | None) -> str:
    return str((path or Path.cwd()).expanduser().resolve())


def _call(tool: str, payload: dict[str, Any], json_mode: bool) -> dict[str, Any]:
    """Run one tool through the shared core and print its result or typed error."""
    fields = BY_NAME[tool].input_model.model_fields
    # An unset option arrives as None; drop it only where None is already the default,
    # so an explicit null (env=None from --no-env) still reaches the contract.
    clean = {
        key: value
        for key, value in payload.items()
        if value is not None or (key in fields and fields[key].default is not None)
    }
    try:
        result = execute(tool, clean, OperationContext(actor="cli"))
    except IRPError as error:
        emit_error(error, json_mode)
        raise typer.Exit(1) from error
    emit(result, json_mode)
    return result


# ---------------------------------------------------------------- intake


@app.command("fetch")
def fetch_command(
    paper: Annotated[
        str, typer.Argument(help="arXiv ID or URL, PDF URL, or local PDF / LaTeX path.")
    ],
    study: StudyOption = None,  # type: ignore[assignment]
    prefer: Annotated[str, typer.Option(help="latex or pdf.")] = "latex",
    parser: Annotated[str, typer.Option(help="auto, pypdf or docling.")] = "auto",
    no_pdf: Annotated[bool, typer.Option("--no-pdf", help="Do not download the PDF.")] = False,
    json_mode: JsonOption = False,
) -> None:
    """Fetch a paper into a new study (fetch_paper)."""
    _call(
        "fetch_paper",
        {
            "study": _study(study),
            "paper": paper,
            "prefer": prefer,
            "parser": parser,
            "with_pdf": not no_pdf,
        },
        json_mode,
    )


@app.command("section")
def section_command(
    ident: Annotated[
        str,
        typer.Argument(
            metavar="ID", help="sec:3, tab:2, eq:loss, abstract, index, page:5, lines:1-80."
        ),
    ],
    study: StudyOption = None,  # type: ignore[assignment]
    offset: int = 0,
    max_lines: Annotated[int, typer.Option("--max-lines")] = 300,
    json_mode: JsonOption = False,
) -> None:
    """Read part of the paper with file and line numbers (get_section)."""
    payload = {"study": _study(study), "id": ident, "offset": offset, "max_lines": max_lines}
    if json_mode:
        _call("get_section", payload, True)
        return
    try:
        result = execute("get_section", payload, OperationContext(actor="cli"))
    except IRPError as error:
        emit_error(error, False)
        raise typer.Exit(1) from error
    if "index" in result:
        emit(result, False)
        return
    typer.echo(f"# {result['title']} ({result['kind']}, {result['lines_total']} lines)")
    typer.echo(result["text"])
    if result.get("next_offset") is not None:
        typer.echo(f"... more: --offset {result['next_offset']}")


@app.command("page")
def page_command(
    page: Annotated[int, typer.Argument(help="1-based page number.")],
    study: StudyOption = None,  # type: ignore[assignment]
    dpi: int = 110,
    json_mode: JsonOption = False,
) -> None:
    """Render one page of the paper PDF to PNG (get_page_image)."""
    _call("get_page_image", {"study": _study(study), "page": page, "dpi": dpi}, json_mode)


# ---------------------------------------------------------------- claims and plan


@claim_app.command("add")
def claim_add(
    statement: Annotated[str, typer.Option(help="Short name, e.g. 'Test accuracy on CIFAR-10'.")],
    metric: Annotated[str, typer.Option(help="Metric name, e.g. test_accuracy.")],
    value: Annotated[str, typer.Option(help="The paper's number as printed, e.g. '94.1%'.")],
    where: Annotated[str, typer.Option(help="e.g. 'Table 2, row 3'.")],
    study: StudyOption = None,  # type: ignore[assignment]
    where_kind: Annotated[str, typer.Option("--where-kind")] = "table",
    source_file: Annotated[str | None, typer.Option("--source-file")] = None,
    source_line: Annotated[int | None, typer.Option("--source-line")] = None,
    page: int | None = None,
    comparator: str = "approx",
    tol_rel: Annotated[
        float | None, typer.Option("--tol-rel", help="Reproduced within this fraction.")
    ] = None,
    tol_abs: Annotated[float | None, typer.Option("--tol-abs")] = None,
    close_rel: Annotated[float | None, typer.Option("--close-rel")] = None,
    close_abs: Annotated[float | None, typer.Option("--close-abs")] = None,
    seeds_in_paper: Annotated[int | None, typer.Option("--seeds-in-paper")] = None,
    notes: str | None = None,
    json_mode: JsonOption = False,
) -> None:
    """Record one claim (add_claim)."""
    _call(
        "add_claim",
        {
            "study": _study(study),
            "statement": statement,
            "metric": metric,
            "value": value,
            "where": where,
            "where_kind": where_kind,
            "source_file": source_file,
            "source_line": source_line,
            "page": page,
            "comparator": comparator,
            "tolerance_rel": tol_rel,
            "tolerance_abs": tol_abs,
            "close_rel": close_rel,
            "close_abs": close_abs,
            "seeds_in_paper": seeds_in_paper,
            "notes": notes,
        },
        json_mode,
    )


@claim_app.command("list")
def claim_list(study: StudyOption = None, json_mode: JsonOption = False) -> None:  # type: ignore[assignment]
    """List claims and their verdicts (list_claims)."""
    _call("list_claims", {"study": _study(study)}, json_mode)


@guess_app.command("add")
def guess_add(
    missing: Annotated[str, typer.Option(help="What the paper left out.")],
    choice: Annotated[str, typer.Option(help="What you chose.")],
    why: Annotated[str, typer.Option(help="Why.")],
    study: StudyOption = None,  # type: ignore[assignment]
    source: str | None = None,
    claim: Annotated[
        list[str] | None, typer.Option("--claim", help="Affected claim id; repeatable.")
    ] = None,
    json_mode: JsonOption = False,
) -> None:
    """Record a guess (add_guess)."""
    _call(
        "add_guess",
        {
            "study": _study(study),
            "missing": missing,
            "choice": choice,
            "why": why,
            "source": source,
            "claims": claim or [],
        },
        json_mode,
    )


@app.command("map")
def map_command(
    element: Annotated[str, typer.Option(help="e.g. 'Eq. 3 (loss)'.")],
    file: Annotated[str, typer.Option(help="File inside code/, e.g. src/loss.py.")],
    line: Annotated[int, typer.Option(help="First implementing line.")],
    study: StudyOption = None,  # type: ignore[assignment]
    end_line: Annotated[int | None, typer.Option("--end-line")] = None,
    paper_ref: Annotated[
        str | None, typer.Option("--paper-ref", help="Index id or label, e.g. eq:3.")
    ] = None,
    note: str | None = None,
    json_mode: JsonOption = False,
) -> None:
    """Map a paper equation or algorithm step to code (map_method)."""
    _call(
        "map_method",
        {
            "study": _study(study),
            "paper_element": element,
            "paper_ref": paper_ref,
            "code_file": file,
            "code_line": line,
            "end_line": end_line,
            "note": note,
        },
        json_mode,
    )


@note_app.command("add")
def note_add(
    kind: Annotated[
        str, typer.Option(help="limitation, deviation, not_checked, author_contact or other.")
    ],
    text: Annotated[str, typer.Option(help="The note.")],
    study: StudyOption = None,  # type: ignore[assignment]
    claim: Annotated[list[str] | None, typer.Option("--claim")] = None,
    json_mode: JsonOption = False,
) -> None:
    """Record a note (add_note)."""
    _call(
        "add_note",
        {"study": _study(study), "kind": kind, "text": text, "claims": claim or []},
        json_mode,
    )


# ---------------------------------------------------------------- build and run


@env_app.command("create")
def env_create(
    study: StudyOption = None,  # type: ignore[assignment]
    name: str = "main",
    backend: Annotated[str, typer.Option(help="uv or docker.")] = "uv",
    python: str = "3.11",
    requirements: Annotated[
        str | None, typer.Option(help="Requirements file inside code/.")
    ] = None,
    package: Annotated[
        list[str] | None, typer.Option("--package", help="Extra package; repeatable.")
    ] = None,
    base_image: Annotated[str | None, typer.Option("--base-image")] = None,
    system_package: Annotated[list[str] | None, typer.Option("--system-package")] = None,
    gpu: bool = False,
    json_mode: JsonOption = False,
) -> None:
    """Create a pinned environment and its lock file (create_env)."""
    _call(
        "create_env",
        {
            "study": _study(study),
            "name": name,
            "backend": backend,
            "python": python,
            "requirements": requirements,
            "packages": package or [],
            "base_image": base_image,
            "system_packages": system_package or [],
            "gpu": gpu,
        },
        json_mode,
    )


@app.command("run", context_settings={"allow_interspersed_args": False})
def run_command(
    command: Annotated[
        list[str], typer.Argument(help="The command, after --, e.g. -- python train.py.")
    ],
    study: StudyOption = None,  # type: ignore[assignment]
    env: Annotated[str, typer.Option(help="Environment name.")] = "main",
    no_env: Annotated[
        bool, typer.Option("--no-env", help="Use the host environment (no lock file).")
    ] = False,
    scope: Annotated[
        str, typer.Option(help="full, shortened or smoke. Only full can count.")
    ] = "full",
    seed: int | None = None,
    cwd: str = ".",
    timeout: Annotated[int, typer.Option(help="Seconds before the run is stopped.")] = 1800,
    detach: Annotated[
        bool, typer.Option("--detach", help="Start in the background; poll with run-status.")
    ] = False,
    no_network: Annotated[
        bool, typer.Option("--no-network", help="Docker only: no network.")
    ] = False,
    memory: Annotated[str | None, typer.Option(help="Docker only: memory cap, e.g. 8g.")] = None,
    no_commit: Annotated[
        bool, typer.Option("--no-commit", help="Do not commit code/ before the run.")
    ] = False,
    note: str | None = None,
    json_mode: JsonOption = False,
) -> None:
    """Run one command in the study's code (run)."""
    joined = command[0] if len(command) == 1 else _shell_join(command)
    result = _call(
        "run",
        {
            "study": _study(study),
            "command": joined,
            "env": None if no_env else env,
            "scope": scope,
            "seed": seed,
            "cwd": cwd,
            "timeout_s": timeout,
            "wait": not detach,
            "network": not no_network,
            "memory_limit": memory,
            "commit": not no_commit,
            "note": note,
        },
        json_mode,
    )
    if result.get("status") == "cancelled":
        # The run was stopped and recorded; exit with the signal's conventional status.
        raise typer.Exit(143 if signal.SIGTERM in _received_signal else 130)


def _shell_join(parts: list[str]) -> str:
    import shlex

    return shlex.join(parts)


@app.command("run-status")
def run_status_command(
    run_id: Annotated[str, typer.Argument(help="Run id, e.g. r3.")],
    study: StudyOption = None,  # type: ignore[assignment]
    wait: Annotated[int, typer.Option(help="Seconds to wait for completion.")] = 0,
    tail: Annotated[int, typer.Option(help="Output lines to show.")] = 20,
    json_mode: JsonOption = False,
) -> None:
    """Show a run's status and output tail (run_status)."""
    _call(
        "run_status",
        {"study": _study(study), "run_id": run_id, "wait_s": wait, "tail_lines": tail},
        json_mode,
    )


@app.command("run-remote", context_settings={"allow_interspersed_args": False})
def run_remote_command(
    command: Annotated[list[str], typer.Argument(help="The command, after --.")],
    gpu: Annotated[str, typer.Option(help="GPU type, e.g. A10G.")],
    hours: Annotated[float, typer.Option(help="Time limit and estimate basis.")],
    study: StudyOption = None,  # type: ignore[assignment]
    env: str = "main",
    provider: str = "modal",
    gpu_count: Annotated[int, typer.Option("--gpu-count")] = 1,
    approve: Annotated[
        bool, typer.Option("--approve", help="You approve the shown estimate.")
    ] = False,
    scope: str = "full",
    seed: int | None = None,
    output: Annotated[
        list[str] | None,
        typer.Option("--output", help="File under code/ to copy back; repeatable."),
    ] = None,
    wait: bool = False,
    note: str | None = None,
    json_mode: JsonOption = False,
) -> None:
    """Run on a paid GPU provider after a cost estimate and approval (run_remote)."""
    joined = command[0] if len(command) == 1 else _shell_join(command)
    _call(
        "run_remote",
        {
            "study": _study(study),
            "command": joined,
            "env": env,
            "provider": provider,
            "gpu": gpu,
            "gpu_count": gpu_count,
            "hours": hours,
            "approved": approve,
            "scope": scope,
            "seed": seed,
            "outputs": output or [],
            "wait": wait,
            "note": note,
        },
        json_mode,
    )


# ---------------------------------------------------------------- measure, judge, report


@app.command("metrics")
def metrics_command(
    run_id: Annotated[str, typer.Argument(help="Completed run id.")],
    study: StudyOption = None,  # type: ignore[assignment]
    name: Annotated[str | None, typer.Option(help="Measurement name.")] = None,
    source: Annotated[
        str, typer.Option(help="stdout, stderr or a file the run wrote, e.g. code/results.json.")
    ] = "stdout",
    key: str | None = None,
    regex: str | None = None,
    json_pointer: Annotated[str | None, typer.Option("--json-pointer")] = None,
    csv_column: Annotated[str | None, typer.Option("--csv-column")] = None,
    reduce: str = "last",
    specs_json: Annotated[
        str | None, typer.Option("--specs-json", help="JSON list of specs for several metrics.")
    ] = None,
    json_mode: JsonOption = False,
) -> None:
    """Extract numbers from a run's output (extract_metrics)."""
    if specs_json is not None:
        specs = json.loads(specs_json)
    else:
        spec = {
            "name": name or key or csv_column or "value",
            "source": source,
            "key": key,
            "regex": regex,
            "json_pointer": json_pointer,
            "csv_column": csv_column,
            "reduce": reduce,
        }
        specs = [{k: v for k, v in spec.items() if v is not None}]
    _call("extract_metrics", {"study": _study(study), "run_id": run_id, "specs": specs}, json_mode)


@app.command("compare")
def compare_command(
    claim_id: Annotated[str, typer.Argument(help="Claim id, e.g. c1.")],
    study: StudyOption = None,  # type: ignore[assignment]
    measurement: Annotated[
        list[str] | None,
        typer.Option("--measurement", "-m", help="Measurement id; repeat per seed."),
    ] = None,
    unit_scale: Annotated[
        float, typer.Option("--unit-scale", help="Power of ten, e.g. 100.")
    ] = 1.0,
    could_not_run: Annotated[bool, typer.Option("--could-not-run")] = False,
    reason: str | None = None,
    blocking_error: Annotated[str | None, typer.Option("--blocking-error")] = None,
    failed_run: Annotated[str | None, typer.Option("--failed-run")] = None,
    context: Annotated[
        list[str] | None, typer.Option("--context", help="Context-only measurement id.")
    ] = None,
    note: str | None = None,
    json_mode: JsonOption = False,
) -> None:
    """Judge a claim: reproduced, close, not reproduced, or could not run (compare)."""
    _call(
        "compare",
        {
            "study": _study(study),
            "claim_id": claim_id,
            "measurement_ids": measurement or [],
            "unit_scale": unit_scale,
            "could_not_run": could_not_run,
            "reason": reason,
            "blocking_error": blocking_error,
            "failed_run_id": failed_run,
            "context_measurement_ids": context or [],
            "note": note,
        },
        json_mode,
    )


@app.command("report")
def report_command(
    study: StudyOption = None,  # type: ignore[assignment]
    draft: Annotated[
        bool, typer.Option("--draft", help="Write a draft even if the gate has not passed.")
    ] = False,
    bundle: Annotated[
        Path | None, typer.Option(help="New directory for a shareable bundle.")
    ] = None,
    json_mode: JsonOption = False,
) -> None:
    """Write report.md and report.json from the evidence log (report)."""
    _call(
        "report",
        {
            "study": _study(study),
            "draft": draft,
            "bundle": str(bundle.expanduser().resolve()) if bundle else None,
        },
        json_mode,
    )


@app.command("verify")
def verify_command(study: StudyOption = None, json_mode: JsonOption = False) -> None:  # type: ignore[assignment]
    """Recheck the hash chain and every recorded file (verify)."""
    result = _call("verify", {"study": _study(study)}, json_mode)
    if not result.get("ok"):
        raise typer.Exit(1)


@app.command("status")
def status_command(study: StudyOption = None, json_mode: JsonOption = False) -> None:  # type: ignore[assignment]
    """Show the study and what blocks the report (study_status)."""
    _call("study_status", {"study": _study(study)}, json_mode)


# ---------------------------------------------------------------- catalog and generic call


@app.command("tools")
def tools_command(json_mode: JsonOption = False) -> None:
    """List every tool with its stage and effects."""
    catalog = [
        {
            "name": c.name,
            "stage": c.stage,
            "summary": c.summary,
            "effects": list(c.effects),
            "read_only": c.read_only,
        }
        for c in CATALOG
    ]
    emit({"tools": catalog}, json_mode)


@app.command("call")
def call_command(
    tool: Annotated[str, typer.Argument(help="Tool name, e.g. add_claim.")],
    input_json: Annotated[str, typer.Option("--input", help="JSON object, or @file.json.")],
    json_mode: JsonOption = True,
) -> None:
    """Call any tool with the exact JSON input its MCP schema takes."""
    raw = (
        Path(input_json[1:]).read_text(encoding="utf-8")
        if input_json.startswith("@")
        else input_json
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        emit_error(
            IRPError(ErrorCode.INVALID_REQUEST, f"--input is not valid JSON: {exc}"), json_mode
        )
        raise typer.Exit(1) from exc
    _call(tool, payload, json_mode)


# ---------------------------------------------------------------- budget (human only)


def _confirm_human(prompt: str) -> bool:
    """Budget changes need a person at a terminal; IRP_ALLOW_NONINTERACTIVE_BUDGET=1 is for CI."""
    if os.environ.get("IRP_ALLOW_NONINTERACTIVE_BUDGET") == "1":
        return False
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        typer.secho(
            "error (needs_confirmation): budget and price changes need a person at a terminal. "
            "Agents must ask the person to run this command.",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    if not typer.confirm(prompt, default=False):
        typer.echo("cancelled; nothing recorded")
        raise typer.Exit(0)
    return True


@budget_app.command("show")
def budget_show(study: StudyOption = None, json_mode: JsonOption = False) -> None:  # type: ignore[assignment]
    """Show the budget, spending and recorded prices."""
    from irp.application.report_ops import budget_summary

    try:
        emit(budget_summary(_study(study)), json_mode)
    except IRPError as error:
        emit_error(error, json_mode)
        raise typer.Exit(1) from error


@budget_app.command("set")
def budget_set(
    usd: Annotated[float, typer.Option(help="Total paid compute budget for this study, in USD.")],
    study: StudyOption = None,  # type: ignore[assignment]
) -> None:
    """Set the study's paid compute budget (a hard cap for run_remote)."""
    from irp.application.report_ops import set_budget

    interactive = _confirm_human(f"Allow up to ${usd:.2f} of paid compute for this study?")
    try:
        record = set_budget(_study(study), usd, interactive=interactive)
    except IRPError as error:
        emit_error(error, False)
        raise typer.Exit(1) from error
    typer.echo(f"budget set to ${usd:.2f} (evidence record {record.seq})")


@budget_app.command("price")
def budget_price(
    gpu: Annotated[str, typer.Option(help="GPU type, e.g. A10G.")],
    usd_per_hour: Annotated[
        float,
        typer.Option(
            "--usd-per-hour", help="Current price per GPU-hour from the provider's pricing page."
        ),
    ],
    study: StudyOption = None,  # type: ignore[assignment]
    provider: str = "modal",
    source_url: Annotated[
        str | None, typer.Option("--source-url", help="Pricing page you read.")
    ] = None,
) -> None:
    """Record a provider's current GPU price for cost estimates."""
    from irp.application.report_ops import set_price
    from irp.providers.compute.pricing import PRICING_PAGES

    interactive = _confirm_human(f"Record {provider} {gpu} at ${usd_per_hour}/GPU-hour?")
    try:
        record = set_price(
            _study(study),
            provider=provider,
            gpu=gpu,
            usd_per_hour=usd_per_hour,
            source_url=source_url or PRICING_PAGES.get(provider),
            interactive=interactive,
        )
    except IRPError as error:
        emit_error(error, False)
        raise typer.Exit(1) from error
    typer.echo(f"price recorded (evidence record {record.seq})")


# ---------------------------------------------------------------- setup, doctor, update, uninstall


@app.command("setup")
def setup_command(
    client: Annotated[
        list[str] | None, typer.Option("--client", help="claude_code, codex or cursor; repeatable.")
    ] = None,
    all_detected: Annotated[
        bool, typer.Option("--all-detected", help="Configure every detected agent.")
    ] = False,
    skill: Annotated[
        bool | None,
        typer.Option("--skill/--no-skill", help="Install the bundled skill (default: yes)."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan; change nothing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Approve the plan without prompting.")
    ] = False,
    json_mode: JsonOption = False,
) -> None:
    """Register IRP with your agents and install the skill, after showing the plan."""
    from irp.application.setup import SetupOptions, run_setup
    from irp.cli.interactive import confirm_plan, render_plan, select_clients

    interactive = (
        not yes and not dry_run and not json_mode and sys.stdin.isatty() and sys.stdout.isatty()
    )
    result = run_setup(
        SetupOptions(
            clients=client or [],
            all_detected=all_detected,
            install_skill=skill,
            dry_run=dry_run,
            approved=yes,
        ),
        select=select_clients if interactive else None,
        confirm=confirm_plan if interactive else None,
    )
    if json_mode:
        emit(result, True)
    else:
        render_plan(result)
    if result["status"] in ("needs_confirmation", "needs_human"):
        raise typer.Exit(1)


@app.command("doctor")
def doctor_command(
    client: Annotated[
        list[str] | None,
        typer.Option("--client", help="Require this agent's registration; repeatable."),
    ] = None,
    skill: Annotated[
        bool, typer.Option("--skill", help="Require the installed skill to match this version.")
    ] = False,
    json_mode: JsonOption = False,
) -> None:
    """Check Python, uv, git, Docker, GPU, disk and agent registration. Changes nothing."""
    from irp.application.doctor import run_doctor
    from irp.cli.interactive import render_doctor

    report = run_doctor(clients=client or [], skill=skill)
    if json_mode:
        emit(report, True)
    else:
        render_doctor(report)
    if not report["healthy"]:
        raise typer.Exit(1)


@app.command("update")
def update_command(json_mode: JsonOption = False) -> None:
    """Update the installation that owns this command, then verify the installed version."""
    from irp.application.update import run_update

    result = run_update(output="structured" if json_mode else "human")
    emit(result, json_mode)
    if result["status"] == "failed":
        raise typer.Exit(1)


@app.command("uninstall")
def uninstall_command(
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    json_mode: JsonOption = False,
) -> None:
    """Remove IRP-owned agent registrations and skill files. Studies are never touched."""
    from irp.application.uninstall import run_uninstall
    from irp.cli.interactive import confirm_plan

    interactive = (
        not yes and not dry_run and not json_mode and sys.stdin.isatty() and sys.stdout.isatty()
    )
    result = run_uninstall(
        approved=yes, dry_run=dry_run, confirm=confirm_plan if interactive else None
    )
    emit(result, json_mode)
    if result["status"] in ("needs_confirmation", "failed"):
        raise typer.Exit(1)


@app.command("mcp")
def mcp_command() -> None:
    """Serve the tools over MCP stdio (what agents launch)."""
    from irp.server.mcp_server import run_stdio

    run_stdio()


_received_signal: list[int] = []


def _handle_sigterm(signum: int, frame: object) -> None:
    _received_signal.append(signum)
    raise KeyboardInterrupt


def run_cli(argv: list[str] | None = None) -> int:
    """Entry point for one-shot commands; Ctrl-C and SIGTERM stop a run and record it as cancelled."""
    import click

    from irp.logging_setup import configure_logging

    arguments = sys.argv[1:] if argv is None else argv
    try:
        configure_logging(default_level="silent")
    except ValueError as exc:
        # Doctor still runs so its report can name the invalid setting.
        if arguments[:1] != ["doctor"]:
            typer.secho(f"error (configuration_invalid): {exc}", err=True, fg=typer.colors.RED)
            return 1
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        result = app(args=arguments, prog_name=PRODUCT.cli_binary, standalone_mode=False)
    except click.exceptions.Abort:
        typer.echo("cancelled", err=True)
        return 143 if signal.SIGTERM in _received_signal else 130
    except click.exceptions.ClickException as exc:
        exc.show()
        return exc.exit_code
    return result if isinstance(result, int) else 0
