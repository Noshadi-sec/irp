"""report, verify, study_status, and the shareable bundle."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
from typing import Any

from irp.application.claims_ops import stale_mappings
from irp.application.context import OperationContext
from irp.application.evidence_log import utc_now
from irp.application.study import (
    Study,
    code_state,
    git_executable,
    open_study,
    resolve_study_path,
    tree_digest,
)
from irp.contracts.inputs import ReportInput, StudyStatusInput, VerifyInput
from irp.domain.errors import ErrorCode, IRPError
from irp.domain.evidence import EvidenceRecord
from irp.domain.gate import completion_gate
from irp.domain.report import build_report, render_markdown
from irp.domain.state import StudyState, replay
from irp.filesystem import atomic_write_text, sha256_file
from irp.identity import EVIDENCE_LOG, PRODUCT, REPORT_JSON, REPORT_MD, STUDY_MANIFEST
from irp.providers.compute.local import SKIP_DIRS

BUNDLE_MARKER = "bundle.json"


def _expected_files(state: StudyState) -> list[dict[str, Any]]:
    """Every file the evidence log vouches for, with the record that vouches for it."""
    files: list[dict[str, Any]] = []
    for item in (state.paper or {}).get("files", []):
        files.append({**item, "owner": "paper", "required": True})
    for env in state.envs.values():
        files.append(
            {
                "path": env["lock_file"],
                "sha256": env["lock_sha256"],
                "owner": f"env {env['name']}",
                "required": True,
            }
        )
        if env.get("dockerfile"):
            files.append(
                {
                    "path": env["dockerfile"],
                    "sha256": env["dockerfile_sha256"],
                    "owner": f"env {env['name']}",
                    "required": True,
                }
            )
    for run_id, run in state.runs.items():
        completed = run.completed or {}
        for stream in ("stdout", "stderr"):
            if completed.get(stream):
                files.append({**completed[stream], "owner": f"run {run_id}", "required": True})
        for output in completed.get("outputs", []):
            if output.get("archived"):
                files.append(
                    {
                        "path": output["archived"],
                        "sha256": output["sha256"],
                        "owner": f"run {run_id}",
                        "required": True,
                    }
                )
            else:
                # Later runs may legitimately overwrite code/ outputs; only archived copies are binding.
                files.append(
                    {
                        "path": output["path"],
                        "sha256": output["sha256"],
                        "owner": f"run {run_id}",
                        "required": False,
                    }
                )
    if state.reports:
        latest = state.reports[-1]
        for key in ("report_md", "report_json"):
            if latest.get(key):
                files.append({**latest[key], "owner": "latest report", "required": True})
    return files


def verify_study(study: Study) -> dict[str, Any]:
    chain = study.log.read()
    state = replay(chain.records)
    bundled = (study.root / BUNDLE_MARKER).is_file()
    problems: list[dict[str, Any]] = []
    informational: list[dict[str, Any]] = []
    checked = 0
    for item in _expected_files(state):
        path = study.root / item["path"]
        present = path.is_dir() if item.get("tree") else path.is_file()
        if not present:
            entry = {"path": item["path"], "owner": item["owner"], "problem": "missing"}
            if bundled and item["owner"] == "paper":
                entry["problem"] = "not included in bundles (the paper is never redistributed)"
                informational.append(entry)
            elif item["required"]:
                problems.append(entry)
            else:
                informational.append(
                    {**entry, "problem": "overwritten or removed after the run (not archived)"}
                )
            continue
        checked += 1
        actual = tree_digest(path) if item.get("tree") else sha256_file(path)
        if actual != item["sha256"]:
            entry = {
                "path": item["path"],
                "owner": item["owner"],
                "problem": "hash mismatch",
                "expected": item["sha256"],
                "actual": actual,
            }
            if item["required"]:
                problems.append(entry)
            else:
                informational.append({**entry, "problem": "changed by a later run (not archived)"})
    ok = chain.ok and not problems
    return {
        "ok": ok,
        "records": len(chain.records),
        "head": chain.head,
        "chain_ok": chain.ok,
        "chain_problems": chain.problems,
        "files_checked": checked,
        "file_problems": problems,
        "informational": informational,
    }


def verify(request: VerifyInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    result = verify_study(study)
    if not result["ok"]:
        result["remediation"] = (
            "Something in this study changed after it was recorded. Restore the named files or the "
            "evidence log from a backup or from git; IRP never repairs evidence."
        )
    return result


def report(request: ReportInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    verification = verify_study(study)
    if not verification["chain_ok"]:
        raise IRPError(
            ErrorCode.VERIFICATION_FAILED,
            "The evidence log fails verification; no report can be written from it.",
            remediation="Run verify and restore the log.",
            details={"problems": verification["chain_problems"][:10]},
        )
    state = study.state()
    stale = stale_mappings(study, state)
    gate = completion_gate(state, stale_mappings=stale)
    if verification["file_problems"]:
        gate["blocking"].append(
            {
                "check": "files_verified",
                "detail": f"{len(verification['file_problems'])} recorded files are missing or changed; run verify.",
            }
        )
        gate["complete"] = False
    final = not request.draft
    if final and not gate["complete"]:
        raise IRPError(
            ErrorCode.INCOMPLETE_STUDY,
            "The completion gate has not passed, so a final report is refused.",
            remediation="Resolve each blocking item (usually: every claim needs a verdict with evidence), "
            "or pass draft=true for a draft.",
            details={"blocking": gate["blocking"], "warnings": gate["warnings"]},
        )
    facts = {
        "final": final,
        "generated_at": utc_now(),
        "tool_version": PRODUCT.version,
        "verification": {
            "ok": verification["ok"],
            "problems": verification["file_problems"] + verification["chain_problems"],
        },
        "stale_mappings": stale,
        "gate": gate,
        "code_state": code_state(study.code_dir, commit_message=None),
        "verify_command": f"{PRODUCT.cli_binary} verify --study {study.root}",
    }
    document = build_report(state, facts)
    markdown = render_markdown(document)
    md_path = study.root / (REPORT_MD if final else "report.draft.md")
    json_path = study.root / (REPORT_JSON if final else "report.draft.json")
    atomic_write_text(json_path, json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    atomic_write_text(md_path, markdown)
    written = {
        "final": final,
        "report_md": {"path": study.rel(md_path), "sha256": sha256_file(md_path)},
        "report_json": {"path": study.rel(json_path), "sha256": sha256_file(json_path)},
        "summary": document["summary"],
        "evidence_head": state.head,
    }
    study.log.append("report.written", written, actor=context.actor)
    result: dict[str, Any] = {
        "final": final,
        "report_md": str(md_path),
        "report_json": str(json_path),
        "summary": document["summary"],
        "warnings": [w["detail"] for w in gate["warnings"]],
    }
    if request.bundle:
        result["bundle"] = bundle_study(study, request.bundle)
    return result


def bundle_study(study: Study, destination_raw: str) -> dict[str, Any]:
    """Copy what a reader needs to check the report; never the paper itself."""
    destination = resolve_study_path(destination_raw)
    if destination.exists() and any(destination.iterdir()):
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"{destination} exists and is not empty.",
            remediation="Choose a new directory for the bundle.",
        )
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    def copy(relative: str) -> None:
        source = study.root / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(relative)

    for name in (
        STUDY_MANIFEST,
        EVIDENCE_LOG,
        REPORT_MD,
        REPORT_JSON,
        "report.draft.md",
        "report.draft.json",
    ):
        copy(name)
    state = study.state()
    for env in state.envs.values():
        for key in ("lock_file", "dockerfile", "requirements_snapshot"):
            if env.get(key):
                copy(env[key])
    for run_id, run in state.runs.items():
        for name in ("stdout.txt", "stderr.txt"):
            copy(f"runs/{run_id}/{name}")
        for output in (run.completed or {}).get("outputs", []):
            if output.get("archived"):
                copy(output["archived"])
    code_target = destination / "code"
    if git_executable() is not None and (study.code_dir / ".git").exists():
        tar_bytes = subprocess.run(
            [git_executable() or "git", "archive", "--format=tar", "HEAD"],
            cwd=study.code_dir,
            capture_output=True,
            check=True,
            timeout=300,
        ).stdout
        code_target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive_file:
            try:
                archive_file.extractall(code_target, filter="data")
            except TypeError:  # Python < 3.11.4 has no extraction filters
                safe = [m for m in archive_file.getmembers() if m.isfile() or m.isdir()]
                archive_file.extractall(code_target, members=safe)  # noqa: S202 - own repo, links dropped
        copied.append("code/ (git HEAD)")
    else:
        shutil.copytree(study.code_dir, code_target, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        copied.append("code/")
    marker = {
        "created_at": utc_now(),
        "created_by": f"{PRODUCT.package_name} {PRODUCT.version}",
        "source_study": str(study.root),
        "excluded": [
            "paper/ (never redistributed; fetch it from the links in report.json)",
            "envs/*/venv",
        ],
    }
    atomic_write_text(destination / BUNDLE_MARKER, json.dumps(marker, indent=2) + "\n")
    return {"path": str(destination), "files": copied}


def study_status(request: StudyStatusInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    gate = completion_gate(state, stale_mappings=stale_mappings(study, state))
    paper = state.paper or {}
    claims = []
    for claim_id, claim in state.claims.items():
        current = state.current_verdict(claim_id)
        claims.append(
            {
                "id": claim_id,
                "statement": claim["statement"],
                "paper": claim["value_text"],
                "where": claim["location"]["label"],
                "verdict": current["verdict"] if current else None,
            }
        )
    return {
        "study": str(study.root),
        "paper": {k: paper.get(k) for k in ("title", "arxiv_id", "version", "source_format")}
        if paper
        else None,
        "claims": claims,
        "guesses": len(state.guesses),
        "method_map": len(state.mappings),
        "notes": len(state.notes),
        "environments": [
            {"name": e["name"], "backend": e["backend"], "python": e.get("python")}
            for e in state.envs.values()
        ],
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "scope": r.started.get("scope"),
                "seed": r.started.get("seed"),
                "counts": r.counts_as_reproduction,
            }
            for r in state.runs.values()
        ],
        "measurements": len(state.measurements),
        "budget": {"budget_usd": state.budget_usd, "spent_usd": state.spent_usd()},
        "gate": gate,
        "evidence": {"records": state.record_count, "head": state.head},
        "next": _next_step(state),
    }


def _next_step(state: StudyState) -> str:
    if state.paper is None:
        return "fetch_paper"
    if not state.claims:
        return "Read the paper (get_section) and record every claim with add_claim before writing code."
    if not state.envs:
        return "Write the implementation in code/, then create_env."
    if not state.runs:
        return "Run the smallest faithful version first with run (scope='full')."
    running = [r.id for r in state.runs.values() if r.completed is None]
    if running:
        return f"Wait for {running[0]} with run_status."
    if not state.measurements:
        return "Extract numbers from a completed run with extract_metrics."
    missing = [cid for cid in state.claims if state.current_verdict(cid) is None]
    if missing:
        return f"Judge {missing[0]} with compare (or record could_not_run)."
    if not state.mappings:
        return "Map each equation or algorithm step to code with map_method, then write the report."
    return "Write the report with report."


def set_budget(study_raw: str, usd: float, *, interactive: bool) -> EvidenceRecord:
    """Human-only: the agent has no MCP tool for this, and the CLI asks on a terminal."""
    if usd < 0:
        raise IRPError(ErrorCode.INVALID_REQUEST, "The budget cannot be negative.")
    study = open_study(study_raw)
    return study.log.append(
        "budget.set", {"budget_usd": round(usd, 2), "interactive": interactive}, actor="cli"
    )


def set_price(
    study_raw: str,
    *,
    provider: str,
    gpu: str,
    usd_per_hour: float,
    source_url: str | None,
    interactive: bool,
) -> EvidenceRecord:
    if usd_per_hour <= 0:
        raise IRPError(ErrorCode.INVALID_REQUEST, "The price must be positive.")
    study = open_study(study_raw)
    return study.log.append(
        "price.set",
        {
            "provider": provider,
            "gpu": gpu,
            "usd_per_hour": usd_per_hour,
            "source_url": source_url,
            "recorded_at": utc_now(),
            "interactive": interactive,
        },
        actor="cli",
    )


def budget_summary(study_raw: str) -> dict[str, Any]:
    study = open_study(study_raw)
    state = study.state()
    return {
        "budget_usd": state.budget_usd,
        "spent_usd": state.spent_usd(),
        "remaining_usd": round(state.budget_usd - state.spent_usd(), 4),
        "prices": list(state.prices.values()),
        "events": state.budget_events,
    }
