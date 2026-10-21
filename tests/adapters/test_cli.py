"""The public CLI: same tools, same evidence, typed errors and exit statuses."""

import json
import sys

import pytest

from irp.cli.app import run_cli
from irp.identity import PRODUCT
from tests.conftest import TOY_CODE
from tests.support.arxiv import TOY_PAPER


def cli(capsys, *args):
    code = run_cli(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_and_help(capsys):
    code, out, _ = cli(capsys, "--version")
    assert code == 0 and out.strip() == PRODUCT.version
    code, out, _ = cli(capsys, "--help")
    assert code == 0 and "Build any paper" in out


def test_full_workflow_through_the_cli(capsys, tmp_path):
    study = str(tmp_path / "s")
    assert cli(capsys, "fetch", str(TOY_PAPER), "--study", study, "--json")[0] == 0
    code, out, _ = cli(capsys, "section", "tab:main", "--study", study)
    assert code == 0 and "OLS (ours) & 2.00 & 0.0100" in out
    code, out, _ = cli(
        capsys,
        "claim",
        "add",
        "--study",
        study,
        "--statement",
        "Slope",
        "--metric",
        "slope",
        "--value",
        "2.00",
        "--where",
        "Table 1",
        "--source-file",
        "main.tex",
        "--source-line",
        "41",
        "--tol-abs",
        "0.02",
        "--json",
    )
    assert code == 0 and json.loads(out)["claim"]["paper_check"]["status"] == "found"
    (tmp_path / "s" / "code" / "ols.py").write_text(TOY_CODE)
    code, out, _ = cli(
        capsys,
        "run",
        "--study",
        study,
        "--no-env",
        "--seed",
        "0",
        "--json",
        "--",
        sys.executable,
        "ols.py",
    )
    assert code == 0 and json.loads(out)["status"] == "succeeded"
    code, out, _ = cli(capsys, "metrics", "r1", "--study", study, "--key", "slope", "--json")
    assert json.loads(out)["measurements"][0]["id"] == "m1"
    code, out, _ = cli(capsys, "compare", "c1", "--study", study, "-m", "m1", "--json")
    assert json.loads(out)["verdict"] == "reproduced"
    assert cli(capsys, "report", "--study", study)[0] == 0
    assert cli(capsys, "verify", "--study", study)[0] == 0
    code, out, _ = cli(capsys, "status", "--study", study, "--json")
    assert json.loads(out)["gate"]["complete"] is True


def test_typed_errors_exit_1_with_json(capsys, tmp_path):
    code, out, _ = cli(capsys, "status", "--study", str(tmp_path / "missing"), "--json")
    assert code == 1
    assert json.loads(out)["error"]["code"] == "study_not_found"
    code, _, err = cli(capsys, "status", "--study", str(tmp_path / "missing"))
    assert code == 1 and "next:" in err


def test_call_accepts_the_exact_mcp_input(capsys, tmp_path):
    study = str(tmp_path / "s")
    cli(capsys, "fetch", str(TOY_PAPER), "--study", study, "--json")
    payload = json.dumps({"study": study, "id": "abstract"})
    code, out, _ = cli(capsys, "call", "get_section", "--input", payload)
    assert code == 0 and "y = 2x + 1" in json.loads(out)["text"]
    code, out, _ = cli(
        capsys, "call", "get_section", "--input", json.dumps({"study": study, "bogus": 1})
    )
    assert code == 1 and json.loads(out)["error"]["code"] == "invalid_request"


def test_budget_needs_a_person_at_a_terminal(capsys, tmp_path):
    study = str(tmp_path / "s")
    cli(capsys, "fetch", str(TOY_PAPER), "--study", study, "--json")
    code, _, err = cli(capsys, "budget", "set", "--usd", "50", "--study", study)
    assert code == 1 and "person at a terminal" in err


def test_invalid_log_level_stops_commands_but_not_doctor(capsys, monkeypatch):
    monkeypatch.setenv("IRP_LOG_LEVEL", "loud")
    assert cli(capsys, "tools")[0] == 1
    _, out, _ = cli(capsys, "doctor", "--json")
    names = {c["name"]: c for c in json.loads(out)["scope_checks"]}
    assert names["log_level"]["ok"] is False


def test_tools_lists_the_catalog(capsys):
    code, out, _ = cli(capsys, "tools", "--json")
    assert code == 0 and len(json.loads(out)["tools"]) == 17


@pytest.mark.parametrize(
    "command", ["setup --dry-run --client claude_code --json", "uninstall --dry-run --json"]
)
def test_maintenance_dry_runs(capsys, command):
    code, out, _ = cli(capsys, *command.split())
    assert code == 0 and json.loads(out)["status"] in ("planned", "nothing_to_remove")


@pytest.mark.parametrize(("sig", "status"), [("SIGINT", 130), ("SIGTERM", 143)])
def test_interrupted_run_is_recorded_as_cancelled(capsys, tmp_path, sig, status):
    import signal
    import subprocess
    import time

    study = str(tmp_path / "s")
    cli(capsys, "fetch", str(TOY_PAPER), "--study", study, "--json")
    cli(
        capsys,
        "claim",
        "add",
        "--study",
        study,
        "--statement",
        "s",
        "--metric",
        "slope",
        "--value",
        "2.00",
        "--where",
        "T",
        "--json",
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "irp",
            "run",
            "--study",
            study,
            "--no-env",
            "--json",
            "--",
            sys.executable,
            "-c",
            "import time; print('started', flush=True); time.sleep(60)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_file = tmp_path / "s" / "runs" / "r1" / "stdout.txt"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not (
        stdout_file.is_file() and "started" in stdout_file.read_text()
    ):
        time.sleep(0.1)
    process.send_signal(getattr(signal, sig))
    process.wait(timeout=30)
    assert process.returncode == status
    records = [
        json.loads(line) for line in (tmp_path / "s" / "evidence.jsonl").read_text().splitlines()
    ]
    assert records[-1]["type"] == "run.completed"
    assert records[-1]["data"]["status"] == "cancelled"
