import pytest

from irp.domain.claims import SuccessBar, build_success_bar, locate_value
from irp.domain.verdicts import aggregate, judge


def bar(**kwargs):
    defaults = {
        "comparator": "approx",
        "tolerance_rel": None,
        "tolerance_abs": None,
        "close_rel": None,
        "close_abs": None,
    }
    return build_success_bar(**{**defaults, **kwargs})


def test_default_bar_is_labeled():
    default = bar()
    assert default.is_default
    assert default.reproduced.rel == 0.01 and default.close.rel == 0.05
    assert not bar(tolerance_abs=0.5).is_default


def test_absolute_bar_derives_close_bound():
    explicit = bar(tolerance_abs=0.5)
    assert explicit.close.abs == 2.5


def test_bar_round_trips_through_records():
    original = bar(comparator="at_least", tolerance_rel=0.02, close_rel=0.1)
    assert SuccessBar.from_dict(original.to_dict()) == original


@pytest.mark.parametrize(
    ("measured", "expected"),
    [(94.1, "reproduced"), (93.2, "reproduced"), (92.0, "close"), (85.0, "not_reproduced")],
)
def test_judge_approx(measured, expected):
    assert judge(94.1, measured, bar(tolerance_rel=0.01, close_rel=0.05)).verdict == expected


def test_judge_at_least_only_penalizes_shortfall():
    speedup = bar(comparator="at_least", tolerance_rel=0.05, close_rel=0.15)
    assert judge(2.0, 3.5, speedup).verdict == "reproduced"
    assert judge(2.0, 1.8, speedup).verdict == "close"
    assert judge(2.0, 1.2, speedup).verdict == "not_reproduced"


def test_judge_at_most_only_penalizes_excess():
    error = bar(comparator="at_most", tolerance_abs=0.1, close_abs=0.5)
    assert judge(5.0, 1.0, error).verdict == "reproduced"
    assert judge(5.0, 5.3, error).verdict == "close"


def test_judge_boundary_is_inclusive():
    assert judge(2.0, 2.01, bar(tolerance_abs=0.01)).verdict == "reproduced"


def test_aggregate_mean_and_sample_std():
    summary = aggregate([93.6, 93.8, 94.0])
    assert summary.value == pytest.approx(93.8)
    assert summary.std == pytest.approx(0.2)
    assert aggregate([1.0]).std is None


def test_locate_value_respects_precision_and_window():
    lines = [
        ("main.tex", 10, "Ours & 94.1 & 81.2"),
        ("main.tex", 11, "Baseline & 94.12"),
        ("main.tex", 40, "acc $94.1\\%$"),
    ]
    assert [m["line"] for m in locate_value("94.1%", lines)] == [10, 40]
    assert [m["line"] for m in locate_value("94.1%", lines, near=("main.tex", 38))] == [40]
    assert locate_value("94.10", [("a.tex", 1, "score 94.12")]) == []
