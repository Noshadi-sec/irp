# Contributing to IRP

IRP welcomes focused bug fixes, documentation improvements, tests, paper
intake and environment improvements, and benchmark work. For contract or
architecture changes, explain the intended scope and link the issue or design
discussion.

## Choosing a contribution

Explain the concrete problem, keep related corrections together, and report the
verification you ran and the coverage you could not run. Collect cosmetic-only
suggestions in an issue rather than separate PRs.

For layering and composition, use the [architecture map](docs/architecture.mermaid).
When adding or changing a tool, follow the [tool design guide](docs/tool-design.md),
update the contract, regenerate the catalog, and add CLI and MCP coverage.

## Reporting issues

Use the issue form that fits. For bugs, include the actual result, the shortest
reproduction you ran, the IRP version, `irp doctor --json` output, and
the smallest useful output. If something is unknown, write `NOT_ENOUGH_INFO` and
explain the gap. Clearly label source-only findings; do not claim results you
did not observe. A root-cause analysis is not required.

To share a reproduction report for the gallery, use the reproduction report
form and attach the bundle from `irp report --bundle`. Never attach the
paper itself.

## Pull request ownership and readiness

AI-assisted contributions are welcome. Every PR has a human owner who takes
responsibility for the complete change, including code, tests, documentation
and claims produced with AI assistance.

Before requesting review, the human owner:

- reviews the final diff and can explain the problem, the approach and its edge cases;
- provides evidence that the change works (focused tests, representative CLI or
  MCP output, CI results), labels source-derived conclusions as such, and never
  reports an unrun check as passing;
- completes the **Author readiness** declaration in the PR template.

AI agents must leave the declaration to the human owner. Readiness requests
review; it does not grant scope approval or permission to merge.

## Contribution scope

IRP builds and checks computational research: paper intake, claims,
environments, runs, measurements, verdicts and evidence reports.

Supported contributions include paper parsers, environment and compute
providers that reuse tools the person already has, metric extraction,
verification, report formats, agent integrations, and benchmarks.

IRP does not integrate or distribute:

- workflows for wet-lab protocols, or for weapons-related or otherwise dangerous science;
- redistribution of papers, datasets or model weights the person did not provide;
- any path that lets an agent set its own budget or approve its own paid compute;
- telemetry, or any call to a model provider from IRP itself.

### Fail-closed integration

If scope fit, side effects, cost exposure, or the verification needed to
establish them remain materially unresolved, **do not merge, enable or ship the
capability**. Record unknowns explicitly; do not turn them into "none". Passing
CI, a finished implementation or maintainer silence is not scope approval.

New compute providers and anything that executes code outside the study need an
explicit maintainer scope decision in the linked issue before substantial
implementation. Small prototypes and draft PRs may inform that decision; they do
not authorize integration.

## Development setup

```bash
uv sync --group dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pytest
```

`uv sync` installs the exact locked dependencies. The pre-commit hook formats and
lints staged files; the pre-push hook runs lint, types and the fast tests.

Before requesting review, run the relevant tests and:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run python scripts/generate_catalog.py --check
```

Packaging, setup and skill changes also need `uv run python scripts/verify_package.py`,
which builds the wheel, installs it into an empty environment, and exercises the
CLI, the stdio MCP catalog and the bundled skill. Docker changes need the Docker
lane (`IRP_TEST_DOCKER=1 uv run pytest -m docker`). State which lanes ran.

### Generated files

`docs/mcp-contracts.md#generated-catalog` is generated from the contracts. The
wheel's `_bundled_skill/` is copied from `.agents/skills/reproduce-paper/` at
build time. Edit the sources, never the outputs.

### Logs and diagnostics

`IRP_LOG_LEVEL` selects `debug`, `info`, `warning`, `error` or `silent`.
Logs go to stderr: MCP defaults to `info`, the one-shot CLI to `silent`, so
stdout carries only protocol messages and results.

## Translations

README translations live in `docs/readme/`. Edit the language's file and check
commands, requirements and claims against the [English README](README.md).

## Maintainer release checklist

Use the [release guide](docs/releasing.md). Pushes to main refresh a Release
Please PR with the next version and changelog. Review it, wait for CI, and merge
it to publish. The release workflow builds once, verifies the exact wheel,
publishes to PyPI through trusted publishing with attestations, and publishes the
MCP Registry entry.
