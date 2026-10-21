# Testing IRP

Use this guide to choose verification for a change.

## Commands

| Command | Scope |
| --- | --- |
| `uv run pytest` | Everything that needs no Docker or network (unit, boundary, CLI, MCP, golden studies, the uv lane when uv is installed) |
| `uv run pytest tests/domain` | Pure logic: evidence chain, numbers, claims, verdicts, metrics, gate, report |
| `uv run pytest tests/providers` | Intake (arXiv parsing, archives, LaTeX, PDF), local execution |
| `uv run pytest tests/application` | Workflows through `execute`, every hard rule, runs, setup, golden studies |
| `uv run pytest tests/adapters` | The public CLI and the in-process MCP server |
| `IRP_TEST_DOCKER=1 uv run pytest -m docker` | Real Docker build and isolated run |
| `uv run python scripts/verify_package.py` | Build the wheel, install it into an empty environment, exercise CLI, stdio MCP, skill and a study |
| `uv run ruff check . && uv run ruff format --check . && uv run mypy` | Static checks |
| `uv run python scripts/generate_catalog.py --check` | Generated docs are current |

On macOS, Docker runs in a VM that shares only some folders; set
`IRP_TEST_DOCKER_DIR` to a directory under your home for the Docker lane.

## Choose verification

| Change | Run |
| --- | --- |
| Domain logic | `tests/domain`, then the golden studies |
| A tool or contract | The tool's application tests, `tests/adapters`, the catalog check |
| A hard rule | Its refusal test in `tests/application/test_rules.py`; never delete one |
| Setup, doctor, update, skill | `tests/application/test_setup.py` and `scripts/verify_package.py` |
| Docker provider | The Docker lane |
| Packaging | `scripts/verify_package.py` |

## Test design

Prefer real public workflows: the CLI and MCP adapters, then
`application.operations.execute`, then unit tests for semantics the workflows
cannot reach. Tests never touch the real home directory: a fixture points
`HOME` at a temporary directory, and setup tests create realistic agent
configuration there.

Network access is never required. `tests/support/arxiv.py` serves the toy
paper as an arXiv e-print tarball, Atom metadata and a PDF built by
`tests/support/pdf.py`.

## Golden studies

`examples/toy-paper/` is a small LaTeX paper with a hidden reference
implementation. The golden tests rebuild it from the text, run three seeds,
judge both claims, write and verify a final report and bundle, detect an edited
report, and check that the rebuild matches the reference output. The uv lane
repeats the study in a real uv environment.

The plan's next golden set is three small published papers with official code
that run on a CPU in under 30 minutes (see [benchmarks](benchmarks.md)); their
studies replay in CI once chosen.

## CI lanes

`ci.yml` runs static checks, the test matrix (Ubuntu and macOS, Python 3.11 to
3.13), the Docker lane, and the package lane that builds, verifies and uploads
the exact wheel. `CI required` gates merges on all of them.
