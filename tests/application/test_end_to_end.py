"""Golden study: the toy paper rebuilt from its text, three seeds, a final report, verification.

The reference implementation in examples/toy-paper/reference plays the hidden
official code: the rebuild must reach the same verdicts.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from irp.domain.errors import IRPError
from tests.conftest import PYTHON, REPO, call, host_run, uv_available

pytestmark = pytest.mark.golden


def judge_all(study: Path, run_ids: list[str]) -> None:
    measurement = 0
    slope_ids, mse_ids = [], []
    for run_id in run_ids:
        call(
            "extract_metrics",
            {
                "study": str(study),
                "run_id": run_id,
                "specs": [
                    {"name": "slope", "key": "slope"},
                    {
                        "name": "test_mse",
                        "source": "code/results.json",
                        "json_pointer": "/test_mse",
                    },
                ],
            },
        )
        slope_ids.append(f"m{measurement + 1}")
        mse_ids.append(f"m{measurement + 2}")
        measurement += 2
    assert (
        call("compare", {"study": str(study), "claim_id": "c1", "measurement_ids": slope_ids})[
            "verdict"
        ]
        == "reproduced"
    )
    assert (
        call("compare", {"study": str(study), "claim_id": "c2", "measurement_ids": mse_ids})[
            "verdict"
        ]
        == "reproduced"
    )


def plan(study: Path) -> None:
    call(
        "add_guess",
        {
            "study": str(study),
            "missing": "Sampling order",
            "choice": "train then test",
            "why": "unstated",
            "claims": ["c1"],
        },
    )
    call(
        "map_method",
        {
            "study": str(study),
            "paper_element": "Eq. 3",
            "paper_ref": "eq:closed",
            "code_file": "ols.py",
            "code_line": 9,
        },
    )


def test_gate_blocks_final_report_until_every_claim_has_a_verdict(coded):
    with pytest.raises(IRPError) as error:
        call("report", {"study": str(coded)})
    assert error.value.code.value == "incomplete_study"
    draft = call("report", {"study": str(coded), "draft": True})
    assert draft["final"] is False
    assert (coded / "report.draft.md").read_text().startswith("> **DRAFT.**")


def test_host_environment_study_reaches_a_verified_final_report(coded, tmp_path):
    plan(coded)
    for seed in (0, 1, 2):
        host_run(coded, seed)
    judge_all(coded, ["r1", "r2", "r3"])
    result = call("report", {"study": str(coded), "bundle": str(tmp_path / "bundle")})
    assert result["final"] is True
    assert result["summary"]["verdicts"]["reproduced"] == 2
    report = json.loads((coded / "report.json").read_text())
    assert report["gate"]["complete"] is True
    assert report["provenance"]["seeds"] == [0, 1, 2]
    assert report["provenance"]["evidence"]["verified"] is True
    markdown = (coded / "report.md").read_text()
    assert "Result: 2 reproduced (of 2 claims)" in markdown
    assert "Eq. 3 -> code/ols.py:9" in markdown
    assert call("verify", {"study": str(coded)})["ok"] is True

    bundle = tmp_path / "bundle"
    assert (bundle / "report.md").is_file() and (bundle / "evidence.jsonl").is_file()
    assert (bundle / "code" / "ols.py").is_file()
    assert not (bundle / "paper").exists(), "the paper is never redistributed"
    bundled = call("verify", {"study": str(bundle)})
    assert bundled["chain_ok"] is True
    assert all(item["owner"] == "paper" for item in bundled["informational"])


def test_edited_report_fails_verification(coded):
    plan(coded)
    host_run(coded, 0)
    judge_all(coded, ["r1"])
    call("report", {"study": str(coded)})
    report = coded / "report.md"
    report.write_text(report.read_text().replace("reproduced", "close"))
    result = call("verify", {"study": str(coded)})
    assert result["ok"] is False
    assert result["file_problems"][0]["path"] == "report.md"


def test_rebuild_matches_the_hidden_reference_code(coded, tmp_path):
    for seed in (0, 1, 2):
        host_run(coded, seed)
    reference = REPO / "examples" / "toy-paper" / "reference" / "fit.py"
    for seed, run_id in zip((0, 1, 2), ("r1", "r2", "r3"), strict=True):
        expected = subprocess.run(
            [sys.executable, str(reference)],
            cwd=tmp_path,
            env={"IRP_SEED": str(seed), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        ours = (coded / "runs" / run_id / "stdout.txt").read_text()
        assert expected.split("slope: ")[1].split()[0] == ours.split("slope: ")[1].split()[0]


@pytest.mark.uv
@pytest.mark.skipif(not uv_available(), reason="uv is not available")
def test_uv_environment_study(coded):
    (coded / "code" / "requirements.txt").write_text("")
    env = call("create_env", {"study": str(coded), "python": PYTHON})
    assert env["env"]["backend"] == "uv" and env["env"]["lock_file"] == "envs/main/lock.txt"
    with pytest.raises(IRPError):
        call("create_env", {"study": str(coded), "python": PYTHON})
    plan(coded)
    for seed in (0, 1, 2):
        result = call("run", {"study": str(coded), "command": "python ols.py", "seed": seed})
        assert result["status"] == "succeeded", result
    judge_all(coded, ["r1", "r2", "r3"])
    call("report", {"study": str(coded)})
    report = json.loads((coded / "report.json").read_text())
    assert report["provenance"]["environments"][0]["python"].startswith(PYTHON)
    assert call("verify", {"study": str(coded)})["ok"] is True
