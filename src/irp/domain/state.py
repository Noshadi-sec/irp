"""Study state, rebuilt only by replaying evidence records.

Nothing else is a source of truth: the CLI, the MCP server and the report all
read this projection, so they cannot disagree about what a study contains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from irp.domain.evidence import EvidenceRecord

ID_PREFIXES = {
    "claim": "c",
    "guess": "g",
    "mapping": "mm",
    "note": "n",
    "run": "r",
    "measurement": "m",
}


@dataclass
class RunState:
    started: dict[str, Any]
    started_seq: int
    completed: dict[str, Any] | None = None
    completed_seq: int | None = None

    @property
    def id(self) -> str:
        return str(self.started["id"])

    @property
    def status(self) -> str:
        if self.completed is None:
            return "running"
        return str(self.completed["status"])

    @property
    def counts_as_reproduction(self) -> bool:
        """Only a full-scope run that exited 0 can support reproduced or close."""
        return (
            self.completed is not None
            and self.completed.get("status") == "succeeded"
            and self.started.get("scope") == "full"
        )


@dataclass
class StudyState:
    study: dict[str, Any] | None = None
    paper: dict[str, Any] | None = None
    claims: dict[str, dict[str, Any]] = field(default_factory=dict)
    guesses: dict[str, dict[str, Any]] = field(default_factory=dict)
    mappings: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: dict[str, dict[str, Any]] = field(default_factory=dict)
    envs: dict[str, dict[str, Any]] = field(default_factory=dict)
    runs: dict[str, RunState] = field(default_factory=dict)
    measurements: dict[str, dict[str, Any]] = field(default_factory=dict)
    verdicts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    budget_usd: float = 0.0
    budget_events: list[dict[str, Any]] = field(default_factory=list)
    prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: list[dict[str, Any]] = field(default_factory=list)
    record_count: int = 0
    head: str | None = None
    first_code_seq: int | None = None
    counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str) -> str:
        """Identifiers are dense and never reused, even across superseded records."""
        prefix = ID_PREFIXES[kind]
        return f"{prefix}{self.counters.get(kind, 0) + 1}"

    def current_verdict(self, claim_id: str) -> dict[str, Any] | None:
        history = self.verdicts.get(claim_id)
        return history[-1] if history else None

    def spent_usd(self) -> float:
        """Committed spend: the approved estimate of every remote run started so far."""
        total = 0.0
        for run in self.runs.values():
            estimate = run.started.get("estimate")
            if run.started.get("compute") not in (None, "local") and estimate:
                completed_cost = (run.completed or {}).get("cost_usd")
                total += float(completed_cost if completed_cost is not None else estimate["usd"])
        return total


def _bump(state: StudyState, kind: str, identifier: str) -> None:
    prefix = ID_PREFIXES[kind]
    number = int(identifier[len(prefix) :])
    state.counters[kind] = max(state.counters.get(kind, 0), number)


def replay(records: list[EvidenceRecord]) -> StudyState:
    """Fold records into state. Unknown or malformed data is left for `verify` to report."""
    state = StudyState()
    for record in records:
        data = record.data
        kind = record.type
        if kind == "study.created":
            state.study = data
        elif kind == "paper.fetched":
            state.paper = data["paper"]
        elif kind == "claim.added":
            claim = data["claim"]
            state.claims[claim["id"]] = claim
            _bump(state, "claim", claim["id"])
        elif kind == "guess.added":
            guess = data["guess"]
            state.guesses[guess["id"]] = guess
            _bump(state, "guess", guess["id"])
        elif kind == "method.mapped":
            mapping = data["mapping"]
            state.mappings[mapping["id"]] = mapping
            _bump(state, "mapping", mapping["id"])
        elif kind == "note.added":
            note = data["note"]
            state.notes[note["id"]] = note
            _bump(state, "note", note["id"])
        elif kind == "env.created":
            env = data["env"]
            state.envs[env["name"]] = env
            if state.first_code_seq is None:
                state.first_code_seq = record.seq
        elif kind == "run.started":
            run = data["run"]
            state.runs[run["id"]] = RunState(started=run, started_seq=record.seq)
            _bump(state, "run", run["id"])
            if state.first_code_seq is None:
                state.first_code_seq = record.seq
        elif kind == "run.completed":
            existing = state.runs.get(data["run_id"])
            if existing is not None:
                existing.completed = data
                existing.completed_seq = record.seq
        elif kind == "metrics.extracted":
            for measurement in data["measurements"]:
                state.measurements[measurement["id"]] = {**measurement, "run_id": data["run_id"]}
                _bump(state, "measurement", measurement["id"])
        elif kind == "verdict.recorded":
            verdict = data["verdict"]
            state.verdicts.setdefault(verdict["claim_id"], []).append(
                {**verdict, "seq": record.seq}
            )
        elif kind == "budget.set":
            state.budget_usd = float(data["budget_usd"])
            state.budget_events.append({**data, "seq": record.seq, "actor": record.actor})
        elif kind == "price.set":
            state.prices[f"{data['provider']}:{data['gpu']}"] = {**data, "seq": record.seq}
        elif kind == "report.written":
            state.reports.append({**data, "seq": record.seq})
        state.record_count += 1
        state.head = record.hash
    return state
