# Repository Guidelines

## Product and Authority

IRP is a local-only tool with shared CLI/MCP workflows that lets an agent
turn a research paper into working code and prove, claim by claim, how close it
gets. IRP never calls a model; the agent decides, IRP acts and records.
Distinguish the paper's claims, measured results, guesses, deviations and
unknowns, and preserve evidence provenance through both adapters.

The report is the product. It is written only from the evidence log, never from
an agent's prose. Every change must keep three properties: a number in a verdict
comes only from a run's own output, tied by hash; the hash chain makes edits to
the log detectable; and the six hard rules in
[the skill](.agents/skills/reproduce-paper/SKILL.md) stay enforced wherever a tool
can enforce them. Do not weaken a rule to make a workflow pass.

Follow the [contribution scope and fail-closed integration rule](CONTRIBUTING.md#contribution-scope).
Do not integrate capabilities while scope, side effects, cost exposure or required
verification remain unresolved. New compute providers, anything that spends
money, and anything that runs code outside the study need a maintainer scope
decision before substantial implementation.

Configuration changes must be additive and idempotent, with backups. Setup must
show its plan and require approval before writing files. Installers must not
install or upgrade unrelated software, including uv, Python, git, Docker or
CUDA. There is no MCP tool that sets a budget or a price; keep it that way.

Never redistribute papers or datasets: bundles exclude `paper/`, and reports
link to sources. Support computational papers only.

## Architecture and Cleanup

Dependencies flow inward: `domain/` (pure: evidence, claims, verdicts, metrics,
gate, report), `contracts/` (tool inputs and catalog), `providers/` (intake,
environments, compute; they depend only on domain and the filesystem
foundation), `application/` (shared CLI/MCP workflows), then the `cli/` and
`server/` adapters. See [docs/architecture.mermaid](docs/architecture.mermaid).

The evidence log is the only source of truth. State is rebuilt by replaying it
(`domain/state.py`); do not add side files that workflows read as results. Each
interpretation has one owner: consumers use the owner's parsed facts instead of
reparsing raw files. Missing coverage is unknown, not absent.

Parse boundary values once and model expected failures as `IRPError` with a
stable code, a remediation and structured details. Keep identity values separate
from display formatting. A rule refusal uses `rule_violation(n, ...)` so the
agent can tell policy from breakage.

When fixing a bug, inspect the producing boundary and its consumers, complete
the directly related refactor in the same change, and remove superseded code.
Passing tests alone do not establish that the brittleness is gone.

## Performance

Optimize in this order: agent tokens and context (compact results, paging,
summaries with access to the complete evidence), then wall time (reuse validated
work; never repeat an identical run), then CPU and memory. Measure before and
after on a representative study when a change affects these costs.

## Development

Use Python 3.11+ and uv.

- `uv sync --group dev`: install locked dependencies.
- `uv run pytest`: the test suite (`-m "not docker"` skips Docker lanes).
- `uv run ruff check . && uv run ruff format --check .`: lint and format.
- `uv run mypy`: strict type checks.
- `uv run python scripts/generate_catalog.py --check`: generated docs are current.
- `uv run python scripts/verify_package.py`: build, install and exercise the wheel.

`docs/mcp-contracts.md#generated-catalog` is generated from `src/irp/contracts`;
edit the contracts and regenerate. Edit the authored skill in
`.agents/skills/reproduce-paper/`; the wheel carries an exact copy. Never commit
studies, `dist/`, virtual environments, credentials, or local planning files.

## Tool and Test Changes

For tool design, follow [docs/tool-design.md](docs/tool-design.md): start from
the agent's question in the workflow, reuse existing contracts, keep CLI and
MCP on the same workflow, and return useful evidence inline.

For tests, follow [docs/testing.md](docs/testing.md). Prefer real public CLI/MCP
workflows, then boundary tests through `application.operations.execute`, then
unit tests for distinct semantics. Every hard rule has a refusal test. Report
unverified coverage explicitly; a simulated provider does not establish
real-provider behavior.

Use Conventional Commit subjects and PR titles. Mark breaking changes with `!` or
a `BREAKING CHANGE:` footer.

## Issue Reports

Follow the matching issue form. Distinguish observed results, source-derived
reasoning and hypotheses. Never claim a run or a measurement you did not
perform. Use `NOT_ENOUGH_INFO` with an explanation for missing answers.

## Pull Request Readiness

AI-assisted contributions are welcome; a human must review and own the final
diff, check the validation evidence, and declare the PR ready. Leave the
template's **Author readiness** declarations for the human owner. Never attest
to human review on their behalf. Report only checks that actually ran.
