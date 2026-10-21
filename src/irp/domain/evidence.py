"""Evidence records and the hash chain that makes edits to the log detectable.

Every action appends one JSON line. A record's `hash` covers all of its other
fields, including `prev`, the hash of the record before it, so changing,
removing or reordering any line breaks every hash after it. The chain proves
the log was not edited after the fact; it does not prove that a person did not
rewrite the whole file, which is why reports also publish the final hash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from irp.domain.canonical import GENESIS_HASH, canonical_json, digest_value
from irp.identity import EVIDENCE_SCHEMA_VERSION

Actor = Literal["cli", "mcp", "runner"]

RECORD_TYPES = frozenset(
    {
        "study.created",
        "paper.fetched",
        "claim.added",
        "guess.added",
        "method.mapped",
        "note.added",
        "env.created",
        "run.started",
        "run.completed",
        "metrics.extracted",
        "verdict.recorded",
        "budget.set",
        "price.set",
        "report.written",
    }
)


@dataclass(frozen=True)
class EvidenceRecord:
    """One line of evidence.jsonl."""

    seq: int
    ts: str
    type: str
    actor: str
    tool_version: str
    data: dict[str, Any]
    prev: str
    hash: str
    schema: int = EVIDENCE_SCHEMA_VERSION

    def body(self) -> dict[str, Any]:
        """All hashed fields: everything except `hash` itself."""
        return {
            "schema": self.schema,
            "seq": self.seq,
            "ts": self.ts,
            "type": self.type,
            "actor": self.actor,
            "tool_version": self.tool_version,
            "data": self.data,
            "prev": self.prev,
        }

    def to_json_line(self) -> str:
        return canonical_json({**self.body(), "hash": self.hash}) + "\n"


def seal_record(
    *,
    seq: int,
    ts: str,
    type: str,
    actor: str,
    tool_version: str,
    data: dict[str, Any],
    prev: str,
) -> EvidenceRecord:
    """Compute the record's hash over its canonical body and return the sealed record."""
    if type not in RECORD_TYPES:
        raise ValueError(f"Unknown evidence record type: {type}")
    body = {
        "schema": EVIDENCE_SCHEMA_VERSION,
        "seq": seq,
        "ts": ts,
        "type": type,
        "actor": actor,
        "tool_version": tool_version,
        "data": data,
        "prev": prev,
    }
    # Canonicalize first: it rejects NaN/Infinity and non-JSON values before
    # anything reaches the log.
    canonical_json(body)
    return EvidenceRecord(
        seq=seq,
        ts=ts,
        type=type,
        actor=actor,
        tool_version=tool_version,
        data=data,
        prev=prev,
        hash=digest_value(body),
    )


@dataclass
class ChainReport:
    """Outcome of re-deriving every hash in the log."""

    records: list[EvidenceRecord] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def head(self) -> str:
        return self.records[-1].hash if self.records else GENESIS_HASH


def parse_and_verify(text: str) -> ChainReport:
    """Parse evidence.jsonl text and recheck sequence, links and hashes.

    Parsing continues past a broken record so the report names every problem,
    not only the first one.
    """
    report = ChainReport()
    expected_prev = GENESIS_HASH
    expected_seq = 0
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    elif lines:
        report.problems.append(
            {
                "kind": "unterminated_line",
                "line": len(lines),
                "detail": "The last record has no newline; a write may have been interrupted.",
            }
        )
    for index, line in enumerate(lines, start=1):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            report.problems.append({"kind": "malformed_json", "line": index, "detail": str(exc)})
            continue
        try:
            record = EvidenceRecord(
                seq=raw["seq"],
                ts=raw["ts"],
                type=raw["type"],
                actor=raw["actor"],
                tool_version=raw["tool_version"],
                data=raw["data"],
                prev=raw["prev"],
                hash=raw["hash"],
                schema=raw["schema"],
            )
        except (KeyError, TypeError) as exc:
            report.problems.append(
                {"kind": "malformed_record", "line": index, "detail": f"missing field {exc}"}
            )
            continue
        extra = set(raw) - {*record.body(), "hash"}
        if extra:
            report.problems.append(
                {"kind": "unexpected_fields", "line": index, "detail": sorted(extra)}
            )
        if record.seq != expected_seq:
            report.problems.append(
                {
                    "kind": "sequence_gap",
                    "line": index,
                    "detail": f"expected seq {expected_seq}, found {record.seq}",
                }
            )
        if record.prev != expected_prev:
            report.problems.append(
                {
                    "kind": "broken_link",
                    "line": index,
                    "detail": f"prev {record.prev} does not match the previous hash {expected_prev}",
                }
            )
        recomputed = digest_value(record.body())
        if recomputed != record.hash:
            report.problems.append(
                {
                    "kind": "hash_mismatch",
                    "line": index,
                    "detail": f"stored {record.hash}, recomputed {recomputed}",
                }
            )
        if record.type not in RECORD_TYPES:
            report.problems.append({"kind": "unknown_type", "line": index, "detail": record.type})
        report.records.append(record)
        expected_prev = record.hash
        expected_seq = record.seq + 1
    return report
