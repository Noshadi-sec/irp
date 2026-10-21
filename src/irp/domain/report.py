"""The evidence report: written only from the evidence log, never from the agent's own words.

A person must be able to check every verdict without trusting the agent, so
each row points at the run, file and line its number came from.
"""

from __future__ import annotations

from typing import Any

from irp.domain.state import StudyState
from irp.domain.verdicts import VERDICT_LABELS, VERDICTS, summarize

REPORT_SCHEMA_VERSION = 1


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}g}"


def _with_unit(value: float | None, unit: str | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    rendered = _fmt(value, digits)
    if unit == "%":
        return f"{rendered}%"
    if unit == "x":
        return f"{rendered}x"
    return f"{rendered} {unit}" if unit else rendered


def _paper_title(state: StudyState) -> str:
    paper = state.paper or {}
    title = paper.get("title") or "Untitled paper"
    if paper.get("arxiv_id"):
        return f"{title} (arXiv {paper['arxiv_id']}{paper.get('version') or ''})"
    return title


def build_report(state: StudyState, facts: dict[str, Any]) -> dict[str, Any]:
    """Assemble report.json. `facts` holds verification and freshness results."""
    claims_out: list[dict[str, Any]] = []
    for claim_id, claim in state.claims.items():
        history = state.verdicts.get(claim_id, [])
        current = history[-1] if history else None
        ours = None
        evidence: list[dict[str, Any]] = []
        if current is not None:
            ours = current.get("aggregate")
            for mid in current.get("measurement_ids", []) + current.get(
                "context_measurement_ids", []
            ):
                measurement = state.measurements.get(mid)
                if measurement is None:
                    continue
                run = state.runs.get(measurement["run_id"])
                evidence.append(
                    {
                        "measurement_id": mid,
                        "run_id": measurement["run_id"],
                        "scope": run.started.get("scope") if run else None,
                        "seed": run.started.get("seed") if run else None,
                        "value": measurement["value"],
                        "source": measurement["source"],
                        "occurrences": measurement["occurrences"][:3],
                        "counts": mid in current.get("measurement_ids", []),
                    }
                )
        claims_out.append(
            {
                "id": claim_id,
                "statement": claim["statement"],
                "metric": claim["metric"],
                "where": claim["location"],
                "paper": {
                    "text": claim["value_text"],
                    "value": claim["value"],
                    "unit": claim.get("unit"),
                },
                "paper_check": claim.get("paper_check"),
                "success_bar": claim["success_bar"],
                "recorded_before_code": claim.get("recorded_before_code", True),
                "verdict": current["verdict"] if current else None,
                "verdict_label": VERDICT_LABELS[current["verdict"]] if current else "no verdict",
                "ours": ours,
                "unit_scale": current.get("unit_scale", 1) if current else None,
                "judgement": current.get("judgement") if current else None,
                "could_not_run": current.get("could_not_run") if current else None,
                "note": current.get("note") if current else None,
                "evidence": evidence,
                "verdict_history": [
                    {
                        "verdict": v["verdict"],
                        "seq": v["seq"],
                        "measurement_ids": v.get("measurement_ids", []),
                    }
                    for v in history
                ],
            }
        )
    verdict_list = [c["verdict"] for c in claims_out if c["verdict"] is not None]
    counts = summarize(verdict_list)
    runs_out = []
    for run_id, run in state.runs.items():
        completed = run.completed or {}
        runs_out.append(
            {
                "id": run_id,
                "command": run.started["command"],
                "env": run.started.get("env"),
                "scope": run.started.get("scope"),
                "seed": run.started.get("seed"),
                "compute": run.started.get("compute", "local"),
                "isolation": run.started.get("isolation"),
                "code_state": run.started.get("code_state"),
                "status": run.status,
                "exit_code": completed.get("exit_code"),
                "duration_s": completed.get("duration_s"),
                "max_rss_bytes": completed.get("max_rss_bytes"),
                "stdout": completed.get("stdout"),
                "stderr": completed.get("stderr"),
                "hardware": completed.get("hardware"),
                "cost_usd": completed.get("cost_usd"),
            }
        )
    seeds = sorted(
        {run["seed"] for run in runs_out if run["seed"] is not None and run["scope"] == "full"}
    )
    paper = state.paper or {}
    return {
        "schema": REPORT_SCHEMA_VERSION,
        "title": _paper_title(state),
        "final": facts["final"],
        "generated_at": facts["generated_at"],
        "tool_version": facts["tool_version"],
        "summary": {
            "claims": len(claims_out),
            "verdicts": counts,
            "without_verdict": [c["id"] for c in claims_out if c["verdict"] is None],
        },
        "claims": claims_out,
        "guesses": list(state.guesses.values()),
        "method_map": [
            {**mapping, "stale": mapping["id"] in facts.get("stale_mappings", [])}
            for mapping in state.mappings.values()
        ],
        "notes": list(state.notes.values()),
        "runs": runs_out,
        "provenance": {
            "paper": {
                "arxiv_id": paper.get("arxiv_id"),
                "version": paper.get("version"),
                "title": paper.get("title"),
                "authors": paper.get("authors"),
                "links": paper.get("links"),
                "source_format": paper.get("source_format"),
                "files": paper.get("files"),
            },
            "code": {
                "runs": _commits_by_run(state),
                "at_report": facts.get("code_state"),
            },
            "environments": list(state.envs.values()),
            "seeds": seeds,
            "commands_logged": len(runs_out),
            "commands_with_exit_code": sum(1 for r in runs_out if r["exit_code"] is not None),
            "budget_usd": state.budget_usd,
            "spent_usd": state.spent_usd(),
            "budget_events": state.budget_events,
            "evidence": {
                "records": state.record_count,
                "head": state.head,
                "verified": facts["verification"]["ok"],
                "problems": facts["verification"]["problems"],
            },
            "verify_command": facts["verify_command"],
        },
        "gate": facts["gate"],
    }


def _commits_by_run(state: StudyState) -> list[dict[str, Any]]:
    """Group runs by the code they ran: a commit (and whether it was clean) or a content digest."""
    groups: dict[str, dict[str, Any]] = {}
    for run_id, run in state.runs.items():
        code = run.started.get("code_state") or {}
        key = code.get("commit") or code.get("tree_sha256") or "unknown"
        group = groups.setdefault(
            key,
            {
                "commit": code.get("commit"),
                "tree_sha256": code.get("tree_sha256"),
                "dirty": False,
                "runs": [],
                "counting_runs": [],
            },
        )
        group["dirty"] = group["dirty"] or bool(code.get("dirty"))
        group["runs"].append(run_id)
        if run.counts_as_reproduction:
            group["counting_runs"].append(run_id)
    return list(groups.values())


def _ours_cell(claim: dict[str, Any]) -> str:
    verdict = claim["verdict"]
    if verdict is None:
        return "no verdict yet"
    if verdict == "could_not_run":
        reason = (claim.get("could_not_run") or {}).get("reason") or "not run"
        return f"not run: {reason}"
    ours = claim.get("ours") or {}
    unit = claim["paper"].get("unit")
    text = _with_unit(ours.get("value"), unit)
    count = ours.get("count") or 0
    if count > 1:
        std = ours.get("std")
        text += f" ({count} seeds, std {_fmt(std, 2)})" if std is not None else f" ({count} seeds)"
    elif count == 1:
        seeds = {e["seed"] for e in claim["evidence"] if e["counts"] and e["seed"] is not None}
        if seeds:
            text += f" (seed {next(iter(seeds))})"
    return text


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    """Human report.md; every statement maps to a field in report.json."""
    lines: list[str] = []
    title = report["title"]
    if not report["final"]:
        lines.append(
            "> **DRAFT.** The completion gate has not passed; this is not a final report.\n"
        )
    lines.append(f"# Reproduction report: {title}\n")
    summary = report["summary"]
    counts = summary["verdicts"]
    parts = [f"{counts[v]} {VERDICT_LABELS[v]}" for v in VERDICTS if counts.get(v)]
    if summary["without_verdict"]:
        parts.append(f"{len(summary['without_verdict'])} without a verdict")
    lines.append(
        f"Result: {', '.join(parts) or 'no verdicts yet'} (of {summary['claims']} claims)\n"
    )
    lines.append("| Claim | Where | Paper | Ours | Verdict |")
    lines.append("| --- | --- | --- | --- | --- |")
    for claim in report["claims"]:
        cells = [
            f"{claim['id']} {claim['statement']}",
            claim["where"]["label"],
            claim["paper"]["text"],
            _ours_cell(claim),
            claim["verdict_label"],
        ]
        lines.append("| " + " | ".join(_escape_cell(c) for c in cells) + " |")
    lines.append("")

    lines.append("## Evidence per claim\n")
    for claim in report["claims"]:
        lines.append(f"### {claim['id']} {claim['statement']}\n")
        bar = claim["success_bar"]
        bar_text = _describe_bar(bar)
        check = claim.get("paper_check") or {}
        if check.get("status") == "found" and check.get("matches"):
            first = check["matches"][0]
            located = f"printed at `{first['file']}:{first['line']}`"
        elif check.get("status") == "not_found":
            located = "not found in the paper text; check it by hand"
        else:
            located = "not checked against the paper text"
        lines.append(f"- Paper: {claim['paper']['text']} ({claim['where']['label']}; {located}).")
        lines.append(f"- Success bar: {bar_text}.")
        if not claim["recorded_before_code"]:
            lines.append("- Recorded after code existed (rule 5).")
        if claim["verdict"] == "could_not_run":
            cnr = claim.get("could_not_run") or {}
            lines.append(f"- Could not run: {cnr.get('reason', '')}")
            lines.append(f"  - Blocking error: `{_escape_inline(cnr.get('blocking_error', ''))}`")
            if cnr.get("run_id"):
                lines.append(f"  - Failed run: {cnr['run_id']}")
        for item in claim["evidence"]:
            source = item["source"]
            where = source["path"]
            occ = item["occurrences"][0] if item["occurrences"] else {}
            if occ.get("line") is not None:
                where += f":{occ['line']}"
            elif occ.get("pointer"):
                where += f"#{occ['pointer']}"
            raw = f' "{_escape_inline(occ["raw"])}"' if occ.get("raw") else ""
            counts = "" if item["counts"] else " (context only; does not count)"
            lines.append(
                f"- {item['measurement_id']} = {_fmt(item['value'], 6)} from run {item['run_id']} "
                f"({item['scope']}, seed {item['seed']}), `{where}`{raw}{counts}"
            )
        if claim.get("unit_scale") not in (None, 1, 1.0):
            lines.append(
                f"- Measured values were multiplied by {claim['unit_scale']:g} to match the paper's unit."
            )
        judgement = claim.get("judgement")
        if judgement:
            lines.append(
                f"- Difference: {_fmt(judgement['difference'], 4)}"
                + (
                    f" ({judgement['relative_difference'] * 100:.2f}% relative)"
                    if judgement.get("relative_difference") is not None
                    else ""
                )
                + "."
            )
        if claim.get("note"):
            lines.append(f"- Note: {claim['note']}")
        if len(claim["verdict_history"]) > 1:
            earlier = ", ".join(v["verdict"] for v in claim["verdict_history"][:-1])
            lines.append(f"- Earlier verdicts for this claim, superseded: {earlier}.")
        lines.append("")

    lines.append("## Guesses\n")
    if report["guesses"]:
        for guess in report["guesses"]:
            source = f" ({guess['source']})" if guess.get("source") else ""
            affects = f" Affects {', '.join(guess['claims'])}." if guess.get("claims") else ""
            lines.append(
                f"- {guess['id']} {guess['missing']}. Choice: {guess['choice']}. Why: {guess['why']}{source}.{affects}"
            )
    else:
        lines.append("- None recorded.")
    lines.append("")

    lines.append("## Method map\n")
    if report["method_map"]:
        for mapping in report["method_map"]:
            end = f"-{mapping['end_line']}" if mapping.get("end_line") else ""
            stale = " (code changed since mapping)" if mapping.get("stale") else ""
            lines.append(
                f"- {mapping['paper_element']} -> {mapping['code_file']}:{mapping['code_line']}{end}{stale}"
            )
    else:
        lines.append("- None recorded.")
    lines.append("")

    if report["notes"]:
        lines.append("## Notes and limitations\n")
        for note in report["notes"]:
            affects = f" ({', '.join(note['claims'])})" if note.get("claims") else ""
            lines.append(f"- {note['id']} [{note['kind']}]{affects}: {note['text']}")
        lines.append("")

    lines.append("## Runs\n")
    if report["runs"]:
        lines.append("| Run | Command | Scope | Seed | Exit | Time | Isolation |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for run in report["runs"]:
            duration = f"{run['duration_s']:.1f}s" if run.get("duration_s") is not None else "n/a"
            exit_code = run["exit_code"] if run["exit_code"] is not None else run["status"]
            cells = [
                run["id"],
                f"`{_escape_inline(run['command'])}`",
                str(run["scope"]),
                str(run["seed"]) if run["seed"] is not None else "-",
                str(exit_code),
                duration,
                str(run.get("isolation") or "none"),
            ]
            lines.append("| " + " | ".join(_escape_cell(c) for c in cells) + " |")
    else:
        lines.append("- No runs.")
    lines.append("")

    lines.append("## Provenance\n")
    prov = report["provenance"]
    paper = prov["paper"]
    if paper.get("arxiv_id"):
        lines.append(f"- Paper: arXiv {paper['arxiv_id']}{paper.get('version') or ''}")
    elif paper.get("title"):
        lines.append(f"- Paper: {paper['title']}")
    for file in paper.get("files") or []:
        lines.append(f"  - `{file['path']}` {file['sha256']}")
    for group in (prov.get("code") or {}).get("runs", []):
        runs = ", ".join(group["runs"])
        if group.get("commit"):
            state = "with uncommitted changes" if group["dirty"] else "clean"
            lines.append(f"- Code: git commit {group['commit']} ({state}) for runs {runs}")
        elif group.get("tree_sha256"):
            lines.append(f"- Code: content digest {group['tree_sha256']} for runs {runs}")
    for env in prov["environments"]:
        python = env.get("python") or "?"
        lines.append(
            f"- Environment {env['name']}: {env['backend']}, Python {python}, lock `{env.get('lock_file')}` "
            f"{env.get('lock_sha256')}"
        )
    gpus = sorted(
        {g for run in report["runs"] for g in ((run.get("hardware") or {}).get("gpus") or [])}
    )
    lines.append(f"- GPU: {', '.join(gpus) if gpus else 'none recorded'}")
    seeds = prov["seeds"]
    lines.append(
        f"- Seeds (full runs): {', '.join(str(s) for s in seeds) if seeds else 'none recorded'}"
    )
    lines.append(
        f"- Commands logged: {prov['commands_logged']}, {prov['commands_with_exit_code']} with an exit code"
    )
    if prov["spent_usd"] or prov["budget_usd"]:
        lines.append(
            f"- Paid compute: ${prov['spent_usd']:.2f} of a ${prov['budget_usd']:.2f} budget"
        )
    evidence = prov["evidence"]
    verified = "verified" if evidence["verified"] else "FAILED verification"
    lines.append(
        f"- Evidence log: {evidence['records']} records, head {evidence['head']}, {verified}"
    )
    lines.append(f"- Verify: `{prov['verify_command']}`")
    lines.append("")
    gate = report["gate"]
    if gate["warnings"]:
        lines.append("## Warnings\n")
        for warning in gate["warnings"]:
            lines.append(f"- {warning['detail']}")
        lines.append("")
    if gate["blocking"]:
        lines.append("## Not finished\n")
        for item in gate["blocking"]:
            lines.append(f"- {item['detail']}")
        lines.append("")
    lines.append(
        f"Generated by IRP {report['tool_version']} from the evidence log at {report['generated_at']}."
    )
    return "\n".join(lines) + "\n"


def _describe_bar(bar: dict[str, Any]) -> str:
    comparator = {
        "approx": "within",
        "at_least": "at least the paper's value minus",
        "at_most": "at most the paper's value plus",
    }[bar["comparator"]]
    reproduced = _tolerance_text(bar["reproduced"])
    close = _tolerance_text(bar["close"])
    default = " (default convention, not a statistical test)" if bar.get("is_default") else ""
    return f"reproduced {comparator} {reproduced}; close {comparator} {close}{default}"


def _tolerance_text(tolerance: dict[str, float]) -> str:
    parts = []
    if "rel" in tolerance:
        parts.append(f"{tolerance['rel'] * 100:g}% relative")
    if "abs" in tolerance:
        parts.append(f"{tolerance['abs']:g} absolute")
    return " or ".join(parts)


def _escape_inline(text: str) -> str:
    return text.replace("`", "'").replace("\n", " ")[:300]
