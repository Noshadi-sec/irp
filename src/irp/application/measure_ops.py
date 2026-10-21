"""extract_metrics and compare: numbers come only from runs, verdicts only from those numbers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from irp.application.context import OperationContext
from irp.application.study import Study, open_study
from irp.contracts.inputs import CompareInput, ExtractMetricsInput, MetricSpec
from irp.domain import metrics
from irp.domain.claims import SuccessBar
from irp.domain.errors import ErrorCode, IRPError, not_found, rule_violation
from irp.domain.numbers import is_power_of_ten
from irp.domain.state import RunState, StudyState
from irp.domain.verdicts import aggregate, judge
from irp.filesystem import sha256_file

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_RECORDED_OCCURRENCES = 20


def _source_file(study: Study, run: RunState, source: str) -> tuple[Path, str, str]:
    """(path to read, study-relative path, expected sha256) for a run-produced source.

    Only the run's own stdout, stderr and the files it wrote qualify; anything
    else could hold a typed number (rule 1).
    """
    completed = run.completed or {}
    if source in ("stdout", "stderr"):
        record = completed[source]
        return study.root / record["path"], record["path"], record["sha256"]
    normalized = source.strip().removeprefix("./")
    for entry in completed.get("outputs", []):
        if normalized in (entry["path"], entry.get("archived")):
            if entry.get("archived"):
                return study.root / entry["archived"], entry["archived"], entry["sha256"]
            return study.root / entry["path"], entry["path"], entry["sha256"]
    raise rule_violation(
        1,
        f"{source} was not written by run {run.id}, so numbers in it cannot count.",
        remediation="Read numbers only from the run's stdout, stderr or files it wrote "
        f"({len(completed.get('outputs', []))} files; see run_status). Make the program print or "
        "save the metric, then run it again.",
        details={"run_outputs": [e["path"] for e in completed.get("outputs", [])][:50]},
    )


def _occurrences(spec: MetricSpec, text: str) -> list[metrics.Occurrence]:
    if spec.key is not None:
        return metrics.key_occurrences(text, spec.key)
    if spec.regex is not None:
        return metrics.regex_occurrences(text, spec.regex)
    if spec.json_pointer is not None:
        return metrics.json_pointer_occurrences(text, spec.json_pointer)
    assert spec.csv_column is not None
    return metrics.csv_occurrences(text, spec.csv_column)


def extract_metrics(request: ExtractMetricsInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    run = state.runs.get(request.run_id)
    if run is None:
        raise not_found("run", request.run_id)
    if run.completed is None:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"Run {request.run_id} has not finished.",
            remediation=f"Wait with run_status run_id='{request.run_id}' wait_s=600.",
        )
    measurements: list[dict[str, Any]] = []
    counter = state.counters.get("measurement", 0)
    for spec in request.specs:
        path, relative, expected = _source_file(study, run, spec.source)
        if not path.is_file():
            raise IRPError(
                ErrorCode.VERIFICATION_FAILED,
                f"{relative} is missing.",
                remediation="Run `irp verify`; the study's files were changed.",
            )
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                f"{relative} is larger than 64 MiB.",
                remediation="Have the program write a small results file.",
            )
        actual = sha256_file(path)
        if actual != expected:
            raise IRPError(
                ErrorCode.VERIFICATION_FAILED,
                f"{relative} changed after run {run.id} wrote it.",
                remediation="Numbers must come from the file as the run left it. Run again to regenerate it.",
                details={"expected": expected, "actual": actual},
            )
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            occurrences = _occurrences(spec, text)
            value, used = metrics.reduce_occurrences(occurrences, spec.reduce)
        except metrics.ExtractionError as exc:
            raise IRPError(
                ErrorCode.NOT_FOUND,
                f"{spec.name}: {exc} (source {relative}).",
                remediation="Check the log with run_status (tail_lines) and adjust the key, regex or pointer.",
            ) from exc
        except ValueError as exc:
            raise IRPError(ErrorCode.INVALID_REQUEST, f"{spec.name}: {exc}") from exc
        counter += 1
        measurements.append(
            {
                "id": f"m{counter}",
                "name": spec.name,
                "value": value,
                "reduce": spec.reduce,
                "spec": spec.model_dump(exclude_none=True),
                "source": {"path": relative, "sha256": expected},
                "occurrences": [o.to_dict() for o in used[:MAX_RECORDED_OCCURRENCES]],
                "occurrence_count": len(occurrences),
            }
        )
    study.log.append(
        "metrics.extracted", {"run_id": run.id, "measurements": measurements}, actor=context.actor
    )
    result: dict[str, Any] = {
        "run_id": run.id,
        "counts": run.counts_as_reproduction,
        "measurements": [
            {
                "id": m["id"],
                "name": m["name"],
                "value": m["value"],
                "source": m["source"]["path"],
                "at": m["occurrences"][0].get("line") or m["occurrences"][0].get("pointer"),
                "raw": m["occurrences"][0]["raw"],
                "matches": m["occurrence_count"],
            }
            for m in measurements
        ],
    }
    if not run.counts_as_reproduction:
        result["warning"] = (
            f"Run {run.id} is a {run.started.get('scope')} run with status {run.status}; these "
            "measurements can be shown as context but never count toward a verdict (rule 4)."
        )
    return result


def _counting_measurements(state: StudyState, ids: list[str]) -> list[dict[str, Any]]:
    selected = []
    seen_runs: set[str] = set()
    for measurement_id in ids:
        measurement = state.measurements.get(measurement_id)
        if measurement is None:
            raise not_found("measurement", measurement_id)
        run = state.runs[measurement["run_id"]]
        if run.started.get("scope") != "full":
            raise rule_violation(
                4,
                f"{measurement_id} comes from {run.started.get('scope')} run {run.id}; shortened and smoke runs never count.",
                remediation="Run the full faithful configuration, or record could_not_run and pass this "
                "measurement as context_measurement_ids.",
            )
        if run.status != "succeeded":
            raise rule_violation(
                3,
                f"{measurement_id} comes from run {run.id}, which ended with status {run.status}.",
                remediation="Fix the run, or record could_not_run with its blocking error.",
            )
        if run.id in seen_runs:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                f"Two measurements come from run {run.id}; one value per run (seed) is averaged.",
            )
        seen_runs.add(run.id)
        selected.append(measurement)
    return selected


def compare(request: CompareInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    claim = state.claims.get(request.claim_id)
    if claim is None:
        raise not_found("claim", request.claim_id)
    for measurement_id in request.context_measurement_ids:
        if measurement_id not in state.measurements:
            raise not_found("measurement", measurement_id)
    verdict: dict[str, Any] = {
        "claim_id": request.claim_id,
        "measurement_ids": [],
        "context_measurement_ids": request.context_measurement_ids,
        "note": request.note,
    }
    if request.could_not_run:
        if request.measurement_ids:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                "could_not_run takes no counting measurements; pass them as context_measurement_ids.",
            )
        if not request.reason or not request.blocking_error:
            raise rule_violation(
                3,
                "'could not run' needs a reason and the exact blocking error.",
                remediation="Pass reason (e.g. 'needs 8 GPUs for 2 days') and blocking_error (the error "
                "message or the constraint).",
            )
        if request.failed_run_id is not None and request.failed_run_id not in state.runs:
            raise not_found("run", request.failed_run_id)
        verdict.update(
            {
                "verdict": "could_not_run",
                "could_not_run": {
                    "reason": request.reason,
                    "blocking_error": request.blocking_error,
                    "run_id": request.failed_run_id,
                },
            }
        )
    else:
        if not request.measurement_ids:
            raise rule_violation(
                1,
                "A measured verdict needs measurement ids from extract_metrics.",
                remediation="Extract the number from a run with extract_metrics, then pass its id.",
            )
        if not is_power_of_ten(request.unit_scale):
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                f"unit_scale must be a power of ten (e.g. 100 or 0.01), got {request.unit_scale}.",
                remediation="unit_scale only converts units; it can never adjust a result.",
            )
        selected = _counting_measurements(state, request.measurement_ids)
        names = {m["name"] for m in selected}
        values = [m["value"] * request.unit_scale for m in selected]
        summary = aggregate(values)
        judgement = judge(claim["value"], summary.value, SuccessBar.from_dict(claim["success_bar"]))
        verdict.update(
            {
                "verdict": judgement.verdict,
                "measurement_ids": request.measurement_ids,
                "unit_scale": request.unit_scale,
                "aggregate": summary.to_dict(),
                "judgement": judgement.to_dict(),
                "metric_names": sorted(names),
            }
        )
    study.log.append("verdict.recorded", {"verdict": verdict}, actor=context.actor)
    result: dict[str, Any] = {"claim_id": request.claim_id, "verdict": verdict["verdict"]}
    if "judgement" in verdict:
        result["paper"] = claim["value_text"]
        result["ours"] = verdict["aggregate"]
        result["difference"] = verdict["judgement"]["difference"]
    warnings = []
    if not request.could_not_run:
        if len({m["name"] for m in _counting_measurements(state, request.measurement_ids)}) > 1:
            warnings.append(
                "The measurements have different names; check they measure the same metric."
            )
        seeds = [
            state.runs[state.measurements[m]["run_id"]].started.get("seed")
            for m in request.measurement_ids
        ]
        if len(seeds) > 1 and len(set(seeds)) < len(seeds):
            warnings.append(
                "Several runs share a seed; averaging them does not add independent evidence."
            )
        if claim.get("seeds_in_paper") and len(request.measurement_ids) < int(
            claim["seeds_in_paper"]
        ):
            warnings.append(
                f"The paper averaged {claim['seeds_in_paper']} runs; this verdict uses {len(request.measurement_ids)}."
            )
    if warnings:
        result["warnings"] = warnings
    remaining = [
        cid
        for cid in state.claims
        if cid != request.claim_id and state.current_verdict(cid) is None
    ]
    result["claims_without_verdict"] = remaining
    return result
