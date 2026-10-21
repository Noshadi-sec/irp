"""The shared core: every tool name bound to exactly one workflow.

The CLI and the MCP server both call `execute`, so a tool behaves the same in
both and every action lands in the same evidence log.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from irp.application import claims_ops, env_ops, measure_ops, paper_ops, report_ops, run_ops
from irp.application.context import OperationContext
from irp.contracts.catalog import BY_NAME, CATALOG
from irp.domain.errors import ErrorCode, IRPError

Handler = Callable[[Any, OperationContext], dict[str, Any]]

HANDLERS: dict[str, Handler] = {
    "fetch_paper": paper_ops.fetch_paper,
    "get_section": paper_ops.get_section,
    "get_page_image": paper_ops.get_page_image,
    "add_claim": claims_ops.add_claim,
    "list_claims": claims_ops.list_claims,
    "add_guess": claims_ops.add_guess,
    "map_method": claims_ops.map_method,
    "add_note": claims_ops.add_note,
    "create_env": env_ops.create_env,
    "run": run_ops.run,
    "run_status": run_ops.run_status,
    "run_remote": run_ops.run_remote,
    "extract_metrics": measure_ops.extract_metrics,
    "compare": measure_ops.compare,
    "report": report_ops.report,
    "verify": report_ops.verify,
    "study_status": report_ops.study_status,
}

# Every contract has exactly one handler; checked at import so a gap fails fast.
_missing = {contract.name for contract in CATALOG} ^ set(HANDLERS)
if _missing:
    raise RuntimeError(f"Contracts and handlers disagree: {sorted(_missing)}")


def validate(name: str, payload: dict[str, Any]) -> BaseModel:
    contract = BY_NAME.get(name)
    if contract is None:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"Unknown tool {name!r}.",
            remediation="List the tools with `irp tools` or MCP tools/list.",
        )
    try:
        return contract.input_model.model_validate(payload)
    except ValidationError as exc:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"Invalid input for {name}.",
            remediation="Correct the listed fields; re-read the tool's input schema if unsure.",
            details={
                "fields": [
                    {"field": ".".join(str(p) for p in error["loc"]), "problem": error["msg"]}
                    for error in exc.errors(include_url=False)
                ]
            },
        ) from exc


def execute(name: str, payload: dict[str, Any], context: OperationContext) -> dict[str, Any]:
    """Validate against the named contract, then run its workflow."""
    request = validate(name, payload)
    return HANDLERS[name](request, context)
