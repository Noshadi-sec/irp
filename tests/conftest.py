"""Shared fixtures: offline papers, studies at each stage, and real uv when available."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from irp.application.context import OperationContext
from irp.application.operations import execute
from tests.support.arxiv import TOY_PAPER, FakeArxiv

REPO = Path(__file__).resolve().parents[1]
# Captured before any fixture isolates HOME; the Docker lane needs the real Docker context.
REAL_HOME = Path(os.environ.get("HOME", str(Path.home())))
PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"

TOY_CODE = """import json, os, random

def sample(rng, n):
    xs = [rng.random() for _ in range(n)]
    return xs, [2.0 * x + 1.0 + rng.gauss(0.0, 0.1) for x in xs]

def fit(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    w = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return w, my - w * mx

seed = int(os.environ["IRP_SEED"])
n = int(os.environ.get("TOY_SAMPLES", "10000"))
rng = random.Random(seed)
train, test = sample(rng, n), sample(rng, n)
w, b = fit(*train)
mse = sum((y - (w * x + b)) ** 2 for x, y in zip(*test)) / n
print(f"slope: {w:.6f}")
print(f"test_mse: {mse:.6f}")
json.dump({"slope": w, "test_mse": mse}, open("results.json", "w"))
"""


def uv_available() -> bool:
    return bool(os.environ.get("IRP_UV") or shutil.which("uv"))


def call(tool: str, payload: dict[str, Any], *, fetcher: Any = None) -> dict[str, Any]:
    context = OperationContext(actor="cli", fetcher=fetcher or FakeArxiv())
    return execute(tool, payload, context)


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Never read or write the real home directory or agent configuration."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for variable in (
        "CLAUDE_CONFIG_DIR",
        "CODEX_HOME",
        "IRP_LOG_LEVEL",
        "MODAL_TOKEN_ID",
        "MODAL_TOKEN_SECRET",
    ):
        monkeypatch.delenv(variable, raising=False)
    yield


@pytest.fixture
def study_dir(tmp_path: Path) -> Iterator[Path]:
    """A fresh study path; IRP_TEST_DOCKER_DIR moves it into a folder a Docker VM can mount."""
    shared = os.environ.get("IRP_TEST_DOCKER_DIR")
    if not shared:
        yield tmp_path / "study"
        return
    root = Path(shared) / f"study-{os.getpid()}-{tmp_path.name}"
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def fetched(study_dir: Path) -> Path:
    """A study with the toy paper fetched from its local LaTeX directory."""
    call("fetch_paper", {"study": str(study_dir), "paper": str(TOY_PAPER)})
    return study_dir


@pytest.fixture
def claimed(fetched: Path) -> Path:
    """Two claims recorded, before any code."""
    for metric, value in (("slope", "2.00"), ("test_mse", "0.0100")):
        call(
            "add_claim",
            {
                "study": str(fetched),
                "statement": metric,
                "metric": metric,
                "value": value,
                "where": "Table 1, row 1",
                "source_file": "main.tex",
                "source_line": 41,
                "tolerance_rel": 0.02,
                "close_rel": 0.05,
            },
        )
    return fetched


@pytest.fixture
def coded(claimed: Path) -> Path:
    (claimed / "code" / "ols.py").write_text(TOY_CODE, encoding="utf-8")
    return claimed


def host_run(
    study: Path, seed: int, *, scope: str = "full", command: str | None = None, **extra: Any
) -> dict[str, Any]:
    """Run with the host interpreter (env=None) so tests need no uv."""
    return call(
        "run",
        {
            "study": str(study),
            "command": command or f"{sys.executable} ols.py",
            "env": None,
            "seed": seed,
            "scope": scope,
            **extra,
        },
    )
