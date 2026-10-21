import json
import sys
import time

import pytest

from irp.application import runner
from irp.application.study import open_study
from irp.domain.errors import IRPError
from tests.conftest import call, host_run


def test_run_records_code_commit_outputs_and_archives(coded):
    result = host_run(coded, 3)
    assert result["status"] == "succeeded" and result["counts"] is True
    assert result["code_state"]["dirty"] is False and len(result["code_state"]["commit"]) == 40
    assert result["outputs"] == ["code/results.json"]
    archived = coded / "runs" / "r1" / "outputs" / "code" / "results.json"
    assert json.loads(archived.read_text())["slope"] > 1.9
    exclude = (coded / "code" / ".git" / "info" / "exclude").read_text()
    assert "/results.json" in exclude, "run outputs stay out of code commits"
    again = host_run(coded, 4)
    assert again["code_state"]["commit"] == result["code_state"]["commit"]
    assert again["code_state"]["dirty"] is False


def test_detached_run_and_status_polling(coded):
    started = host_run(coded, 1, wait=False)
    assert started["status"] == "running"
    status = call("run_status", {"study": str(coded), "run_id": "r1", "wait_s": 60})
    assert status["status"] == "succeeded"
    assert "slope:" in status["stdout_tail"]
    records = [json.loads(line) for line in (coded / "evidence.jsonl").read_text().splitlines()]
    completed = [r for r in records if r["type"] == "run.completed"]
    assert completed[0]["actor"] == "runner"


def test_one_run_at_a_time(coded):
    host_run(coded, 1, wait=False, command=f"{sys.executable} -c 'import time; time.sleep(3)'")
    with pytest.raises(IRPError) as error:
        host_run(coded, 2)
    assert "still running" in error.value.message
    call("run_status", {"study": str(coded), "run_id": "r1", "wait_s": 60})


def test_timeout_is_recorded(coded):
    result = host_run(
        coded, 0, command=f"{sys.executable} -c 'import time; time.sleep(30)'", timeout_s=1
    )
    assert result["status"] == "timeout" and result["counts"] is False


def test_lost_runs_are_recorded_once_the_owner_stops(coded, monkeypatch):
    study = open_study(str(coded))
    study.log.append(
        "run.started",
        {
            "run": {
                "id": "r1",
                "command": "x",
                "scope": "full",
                "launcher": ["true"],
                "requested_at": "2020-01-01T00:00:00.000Z",
                "code_state": {},
            }
        },
        actor="cli",
    )
    assert runner.mark_lost_runs(study, actor="cli") == ["r1"]
    status = call("run_status", {"study": str(coded), "run_id": "r1"})
    assert status["status"] == "error"
    assert "stopped without recording a result" in status["error"]


def test_docker_only_options_need_docker(coded):
    with pytest.raises(IRPError):
        host_run(coded, 0, network=False)


def test_heartbeat_marks_live_runs(coded, monkeypatch):
    monkeypatch.setattr(runner, "HEARTBEAT_INTERVAL_S", 0.05)
    beat = runner.Heartbeat(coded / "runs" / "rX" / "heartbeat")
    with beat:
        time.sleep(0.2)
    age = runner.heartbeat_age(open_study(str(coded)), "rX")
    assert age is not None and age < 5
