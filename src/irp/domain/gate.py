"""The completion gate: a study is finished only when every claim has a verdict with evidence."""

from __future__ import annotations

from typing import Any

from irp.domain.state import StudyState


def completion_gate(
    state: StudyState, *, stale_mappings: list[str] | None = None
) -> dict[str, Any]:
    """Return blocking problems and warnings. Blocking problems stop a final report."""
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if state.paper is None:
        blocking.append({"check": "paper_fetched", "detail": "No paper has been fetched."})
    if not state.claims:
        blocking.append(
            {
                "check": "claims_recorded",
                "detail": "No claims are recorded. Record every claim first.",
            }
        )

    missing = [cid for cid in state.claims if state.current_verdict(cid) is None]
    if missing:
        blocking.append(
            {
                "check": "every_claim_has_verdict",
                "detail": "Claims without a verdict: " + ", ".join(missing),
                "claims": missing,
            }
        )

    for claim_id in state.claims:
        verdict = state.current_verdict(claim_id)
        if verdict is None:
            continue
        if verdict["verdict"] in ("reproduced", "close", "not_reproduced"):
            unsupported = [
                mid
                for mid in verdict.get("measurement_ids", [])
                if mid not in state.measurements
                or not _measurement_counts(state, state.measurements[mid])
            ]
            if not verdict.get("measurement_ids") or unsupported:
                blocking.append(
                    {
                        "check": "verdict_evidence",
                        "detail": f"{claim_id}: the verdict is not backed by measurements from "
                        "completed full-scope runs.",
                        "claims": [claim_id],
                    }
                )
        elif verdict["verdict"] == "could_not_run":
            details = verdict.get("could_not_run") or {}
            if not details.get("blocking_error"):
                blocking.append(
                    {
                        "check": "could_not_run_has_error",
                        "detail": f"{claim_id}: 'could not run' needs the blocking error.",
                        "claims": [claim_id],
                    }
                )

    running = [rid for rid, run in state.runs.items() if run.completed is None]
    if running:
        warnings.append(
            {"check": "runs_finished", "detail": "Runs still in progress: " + ", ".join(running)}
        )
    defaults = [cid for cid, c in state.claims.items() if c["success_bar"].get("is_default")]
    if defaults:
        warnings.append(
            {
                "check": "explicit_success_bar",
                "detail": "These claims use the default tolerance (a convention, not a statistical "
                "test): " + ", ".join(defaults),
                "claims": defaults,
            }
        )
    unlocated = [
        cid
        for cid, c in state.claims.items()
        if (c.get("paper_check") or {}).get("status") != "found"
    ]
    if unlocated:
        warnings.append(
            {
                "check": "claim_value_in_paper",
                "detail": "The paper's value could not be located in the paper text for: "
                + ", ".join(unlocated),
                "claims": unlocated,
            }
        )
    late = [cid for cid, c in state.claims.items() if not c.get("recorded_before_code", True)]
    if late:
        warnings.append(
            {
                "check": "claims_before_code",
                "detail": "Recorded after code existed (rule 5): " + ", ".join(late),
                "claims": late,
            }
        )
    if state.claims and not state.mappings:
        warnings.append(
            {
                "check": "method_map",
                "detail": "No equation or algorithm step is mapped to code; call map_method.",
            }
        )
    if stale_mappings:
        warnings.append(
            {
                "check": "method_map_current",
                "detail": "Mapped code changed after mapping: " + ", ".join(stale_mappings),
                "mappings": stale_mappings,
            }
        )
    dirty = [
        rid
        for rid, run in state.runs.items()
        if run.started.get("code_state", {}).get("dirty") is True
    ]
    if dirty:
        warnings.append(
            {
                "check": "runs_on_committed_code",
                "detail": "Runs started on uncommitted code: " + ", ".join(dirty),
            }
        )
    return {"complete": not blocking, "blocking": blocking, "warnings": warnings}


def _measurement_counts(state: StudyState, measurement: dict[str, Any]) -> bool:
    run = state.runs.get(measurement["run_id"])
    return run is not None and run.counts_as_reproduction
