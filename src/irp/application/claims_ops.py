"""Claims, guesses, method map entries and notes."""

from __future__ import annotations

from typing import Any

from irp.application.context import OperationContext
from irp.application.paper_ops import _load_index, load_lines, resolve_reference
from irp.application.study import Study, code_has_content, head_commit, open_study
from irp.contracts.inputs import (
    AddClaimInput,
    AddGuessInput,
    AddNoteInput,
    ListClaimsInput,
    MapMethodInput,
)
from irp.domain.claims import PaperLocation, build_success_bar, claim_value, locate_value
from irp.domain.errors import ErrorCode, IRPError, not_found
from irp.domain.state import StudyState
from irp.filesystem import contained_path, sha256_file


def _require_paper(state: StudyState) -> None:
    if state.paper is None:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            "The paper has not been fetched for this study.",
            remediation="Call fetch_paper first.",
        )


def _require_claims_exist(state: StudyState, claim_ids: list[str]) -> None:
    for claim_id in claim_ids:
        if claim_id not in state.claims:
            raise not_found("claim", claim_id)


def add_claim(request: AddClaimInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    _require_paper(state)
    try:
        value, unit = claim_value(request.value)
    except ValueError as exc:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"No number in value {request.value!r}.",
            remediation="Pass the paper's number exactly as printed, e.g. '94.1%'.",
        ) from exc
    lines = load_lines(study)
    if (request.source_file is None) != (request.source_line is None):
        raise IRPError(
            ErrorCode.INVALID_REQUEST, "Give source_file and source_line together, or neither."
        )
    near = None
    if request.source_file is not None and request.source_line is not None:
        known = {(file, number) for file, number, _text in lines}
        if (request.source_file, request.source_line) not in known:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                f"{request.source_file}:{request.source_line} is not a line of the paper.",
                remediation="Use a file and line exactly as get_section shows them.",
            )
        near = (request.source_file, request.source_line)
    matches = locate_value(request.value, lines, near=near)
    if near is not None and not matches:
        elsewhere = locate_value(request.value, lines)
        paper_check: dict[str, Any] = {
            "status": "not_found",
            "detail": f"{request.value} is not printed within 3 lines of {near[0]}:{near[1]}.",
            "elsewhere": elsewhere,
        }
    elif matches:
        paper_check = {"status": "found", "matches": matches}
    else:
        paper_check = {
            "status": "not_found",
            "detail": f"{request.value} is not printed anywhere in the extracted paper text.",
        }
    bar = build_success_bar(
        comparator=request.comparator,
        tolerance_rel=request.tolerance_rel,
        tolerance_abs=request.tolerance_abs,
        close_rel=request.close_rel,
        close_abs=request.close_abs,
    )
    location = PaperLocation(
        kind=request.where_kind,
        label=request.where,
        source_file=request.source_file,
        source_line=request.source_line,
        page=request.page,
    )
    before_code = state.first_code_seq is None and not code_has_content(study.code_dir)
    claim = {
        "id": state.next_id("claim"),
        "statement": request.statement,
        "metric": request.metric,
        "value_text": request.value,
        "value": value,
        "unit": unit,
        "location": location.to_dict(),
        "success_bar": bar.to_dict(),
        "seeds_in_paper": request.seeds_in_paper,
        "notes": request.notes,
        "paper_check": paper_check,
        "recorded_before_code": before_code,
    }
    study.log.append("claim.added", {"claim": claim}, actor=context.actor)
    warnings: list[str] = []
    if paper_check["status"] != "found":
        warnings.append(paper_check["detail"] + " Check the value and its location.")
    if bar.is_default:
        warnings.append(
            "No success bar was given; the default (1% relative reproduced, 5% close) is a convention. "
            "State the bar the paper's variance supports."
        )
    if not before_code:
        warnings.append(
            "Code already exists, so this claim is flagged as recorded after code (rule 5)."
        )
    return {"claim": claim, "warnings": warnings}


def list_claims(request: ListClaimsInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    return {"claims": [_claim_summary(state, claim_id) for claim_id in state.claims]}


def _claim_summary(state: StudyState, claim_id: str) -> dict[str, Any]:
    claim = state.claims[claim_id]
    current = state.current_verdict(claim_id)
    return {
        "id": claim_id,
        "statement": claim["statement"],
        "metric": claim["metric"],
        "paper": claim["value_text"],
        "where": claim["location"]["label"],
        "success_bar": claim["success_bar"],
        "paper_check": claim["paper_check"]["status"],
        "verdict": current["verdict"] if current else None,
        "ours": (current or {}).get("aggregate"),
    }


def add_guess(request: AddGuessInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    _require_paper(state)
    _require_claims_exist(state, request.claims)
    guess = {
        "id": state.next_id("guess"),
        "missing": request.missing,
        "choice": request.choice,
        "why": request.why,
        "source": request.source,
        "claims": request.claims,
    }
    study.log.append("guess.added", {"guess": guess}, actor=context.actor)
    return {"guess": guess}


def map_method(request: MapMethodInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    _require_paper(state)
    path = contained_path(study.code_dir, request.code_file, what="code_file")
    if not path.is_file():
        raise IRPError(
            ErrorCode.NOT_FOUND,
            f"code/{request.code_file} does not exist.",
            remediation="Write the implementation first, then map it.",
        )
    text_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    end_line = request.end_line or request.code_line
    if (
        request.code_line > len(text_lines)
        or end_line > len(text_lines)
        or end_line < request.code_line
    ):
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"code/{request.code_file} has {len(text_lines)} lines; {request.code_line}-{end_line} is out of range.",
        )
    paper_entry = None
    if request.paper_ref is not None:
        entry = resolve_reference(_load_index(study), request.paper_ref)
        if entry is None:
            raise IRPError(
                ErrorCode.NOT_FOUND,
                f"{request.paper_ref!r} is not in the paper's index.",
                remediation="Use an id or label from get_section id='index'.",
            )
        paper_entry = {"id": entry["id"], "start": entry.get("start")}
    mapping = {
        "id": state.next_id("mapping"),
        "paper_element": request.paper_element,
        "paper_ref": paper_entry,
        "code_file": f"code/{study.rel(path).removeprefix('code/')}",
        "code_line": request.code_line,
        "end_line": request.end_line,
        "snippet": text_lines[request.code_line - 1].strip()[:200],
        "code_sha256": sha256_file(path),
        "code_commit": head_commit(study.code_dir),
        "note": request.note,
    }
    study.log.append("method.mapped", {"mapping": mapping}, actor=context.actor)
    return {"mapping": mapping}


def stale_mappings(study: Study, state: StudyState) -> list[str]:
    """Mappings whose file changed (or disappeared) since they were recorded."""
    stale = []
    for mapping_id, mapping in state.mappings.items():
        path = study.root / mapping["code_file"]
        if not path.is_file() or sha256_file(path) != mapping["code_sha256"]:
            stale.append(mapping_id)
    return stale


def add_note(request: AddNoteInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    _require_claims_exist(state, request.claims)
    note = {
        "id": state.next_id("note"),
        "kind": request.kind,
        "text": request.text,
        "claims": request.claims,
    }
    study.log.append("note.added", {"note": note}, actor=context.actor)
    return {"note": note}
