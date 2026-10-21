"""Tagged error algebra shared by every adapter.

Each expected failure carries a stable code, a plain message, a remediation the
agent or person can act on, and optional structured details. CLI and MCP project
the same error unchanged, so a caller never has to parse prose to recover.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    STUDY_NOT_FOUND = "study_not_found"
    STUDY_INVALID = "study_invalid"
    PAPER_UNAVAILABLE = "paper_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NOT_FOUND = "not_found"
    RULE_VIOLATION = "rule_violation"
    EXECUTION_FAILURE = "execution_failure"
    TIMEOUT = "timeout"
    VERIFICATION_FAILED = "verification_failed"
    INCOMPLETE_STUDY = "incomplete_study"
    CONFIGURATION_INVALID = "configuration_invalid"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CANCELLED = "cancelled"


# The skill's hard rules, numbered as in SKILL.md. A rule violation names the
# rule so the agent can tell a policy refusal from a broken tool.
HARD_RULES: dict[int, str] = {
    1: "Never type, estimate or copy a number as a result.",
    2: "Never change the paper's method to make a run succeed; record a guess instead.",
    3: 'Report "could not run" with the blocking error instead of pushing through.',
    4: "Run the smallest faithful version first; shortened runs never count.",
    5: "Record every claim before writing any code.",
    6: "Ask before any paid compute.",
}


class IRPError(Exception):
    """An expected, typed failure with a remediation."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        remediation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.remediation is not None:
            payload["remediation"] = self.remediation
        if self.details:
            payload["details"] = self.details
        return payload


def rule_violation(
    rule: int, message: str, *, remediation: str, details: dict[str, Any] | None = None
) -> IRPError:
    """Refuse an action that would break one of the skill's hard rules."""
    return IRPError(
        ErrorCode.RULE_VIOLATION,
        message,
        remediation=remediation,
        details={"rule": rule, "rule_text": HARD_RULES[rule], **(details or {})},
    )


def invalid_request(message: str, **details: Any) -> IRPError:
    return IRPError(ErrorCode.INVALID_REQUEST, message, details=details or None)


def not_found(kind: str, identifier: str, *, remediation: str | None = None) -> IRPError:
    return IRPError(
        ErrorCode.NOT_FOUND,
        f"No {kind} with id {identifier!r} in this study.",
        remediation=remediation or f"Call study_status to list recorded {kind}s.",
        details={"kind": kind, "id": identifier},
    )
