"""Each hard rule the tools can enforce, refused with the rule's number."""

import sys

import pytest

from irp.domain.errors import IRPError
from tests.conftest import call, host_run


def refused(rule: int, tool: str, payload: dict) -> IRPError:
    with pytest.raises(IRPError) as error:
        call(tool, payload)
    assert error.value.code.value == "rule_violation", error.value.to_dict()
    assert error.value.details["rule"] == rule
    return error.value


def test_rule_5_no_environment_or_run_before_claims(fetched):
    refused(5, "create_env", {"study": str(fetched)})
    refused(5, "run", {"study": str(fetched), "command": "true", "env": None})


def test_rule_5_claims_after_code_are_flagged(fetched):
    (fetched / "code" / "train.py").write_text("print(1)\n")
    result = call(
        "add_claim",
        {
            "study": str(fetched),
            "statement": "s",
            "metric": "slope",
            "value": "2.00",
            "where": "Table 1",
        },
    )
    assert result["claim"]["recorded_before_code"] is False
    assert any("rule 5" in w for w in result["warnings"])


def test_rule_1_numbers_only_from_files_the_run_wrote(coded):
    host_run(coded, 0)
    (coded / "code" / "typed.txt").write_text("slope: 2.00\n")
    refused(
        1,
        "extract_metrics",
        {
            "study": str(coded),
            "run_id": "r1",
            "specs": [{"name": "s", "source": "code/typed.txt", "key": "slope"}],
        },
    )
    refused(1, "compare", {"study": str(coded), "claim_id": "c1"})


def test_rule_1_edited_log_is_refused(coded):
    host_run(coded, 0)
    stdout = coded / "runs" / "r1" / "stdout.txt"
    stdout.write_text(stdout.read_text().replace("slope:", "slope: 2.0 #"))
    with pytest.raises(IRPError) as error:
        call(
            "extract_metrics",
            {"study": str(coded), "run_id": "r1", "specs": [{"name": "s", "key": "slope"}]},
        )
    assert error.value.code.value == "verification_failed"


def test_rule_4_shortened_runs_never_count(coded):
    host_run(coded, 0, scope="shortened", command=f"TOY_SAMPLES=100 {sys.executable} ols.py")
    result = call(
        "extract_metrics",
        {"study": str(coded), "run_id": "r1", "specs": [{"name": "slope", "key": "slope"}]},
    )
    assert result["counts"] is False and "rule 4" in result["warning"]
    refused(4, "compare", {"study": str(coded), "claim_id": "c1", "measurement_ids": ["m1"]})
    recorded = call(
        "compare",
        {
            "study": str(coded),
            "claim_id": "c1",
            "could_not_run": True,
            "reason": "full run skipped in this test",
            "blocking_error": "test constraint",
            "context_measurement_ids": ["m1"],
        },
    )
    assert recorded["verdict"] == "could_not_run"


def test_rule_3_failed_runs_do_not_count_and_could_not_run_needs_the_error(coded):
    host_run(coded, 0, command=f"{sys.executable} ols.py && exit 7")
    call(
        "extract_metrics",
        {"study": str(coded), "run_id": "r1", "specs": [{"name": "slope", "key": "slope"}]},
    )
    refused(3, "compare", {"study": str(coded), "claim_id": "c1", "measurement_ids": ["m1"]})
    refused(
        3, "compare", {"study": str(coded), "claim_id": "c1", "could_not_run": True, "reason": "x"}
    )


def test_rule_6_paid_compute_needs_price_budget_and_approval(coded):
    from irp.application.report_ops import set_budget, set_price

    # No environment yet: the remote run needs one for its requirements.
    with pytest.raises(IRPError):
        call(
            "run_remote",
            {"study": str(coded), "command": "python ols.py", "gpu": "A10G", "hours": 1},
        )
    _fake_env(coded)
    refused(
        6,
        "run_remote",
        {"study": str(coded), "command": "python ols.py", "gpu": "A10G", "hours": 1},
    )
    set_price(
        str(coded),
        provider="modal",
        gpu="A10G",
        usd_per_hour=1.5,
        source_url=None,
        interactive=False,
    )
    error = refused(
        6,
        "run_remote",
        {"study": str(coded), "command": "python ols.py", "gpu": "A10G", "hours": 2},
    )
    assert error.details["estimate"]["usd"] == 3.0
    set_budget(str(coded), 10.0, interactive=False)
    with pytest.raises(IRPError) as approval:
        call(
            "run_remote",
            {"study": str(coded), "command": "python ols.py", "gpu": "A10G", "hours": 2},
        )
    assert approval.value.code.value == "needs_confirmation"
    assert approval.value.details["estimate"]["usd"] == 3.0
    with pytest.raises(IRPError) as unavailable:
        call(
            "run_remote",
            {
                "study": str(coded),
                "command": "python ols.py",
                "gpu": "A10G",
                "hours": 2,
                "approved": True,
            },
        )
    assert unavailable.value.code.value == "provider_unavailable"
    status = call("study_status", {"study": str(coded)})
    assert status["budget"] == {"budget_usd": 10.0, "spent_usd": 0.0}
    assert status["runs"] == [], "a refused paid run records nothing"


def test_unit_scale_cannot_hide_a_fudge_factor(coded):
    host_run(coded, 0)
    call(
        "extract_metrics",
        {"study": str(coded), "run_id": "r1", "specs": [{"name": "slope", "key": "slope"}]},
    )
    with pytest.raises(IRPError) as error:
        call(
            "compare",
            {"study": str(coded), "claim_id": "c1", "measurement_ids": ["m1"], "unit_scale": 1.02},
        )
    assert "power of ten" in error.value.message


def _fake_env(study):
    """Record an environment without uv, for gate tests that never run it."""
    from irp.application.study import open_study

    lock = study / "envs" / "main" / "lock.txt"
    lock.parent.mkdir(parents=True)
    lock.write_text("")
    open_study(str(study)).log.append(
        "env.created",
        {
            "env": {
                "name": "main",
                "backend": "uv",
                "requested_python": "3.11",
                "python": "3.11.9",
                "lock_file": "envs/main/lock.txt",
                "lock_sha256": "sha256:"
                + "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "isolation": "none",
                "venv": "envs/main/venv",
            }
        },
        actor="cli",
    )
