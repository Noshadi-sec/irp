import pytest

from irp.domain import metrics

LOG = """epoch 1 | val_acc: 0.81 loss=0.9
epoch 2 | val_acc: 0.86 loss=0.5
"test_acc": 0.938,
final test_acc: 93.9%
"""


def test_key_occurrences_cover_common_forms():
    found = metrics.key_occurrences(LOG, "test_acc")
    assert [o.value for o in found] == [0.938, 93.9]
    assert [o.line for o in found] == [3, 4]
    assert [o.value for o in metrics.key_occurrences(LOG, "loss")] == [0.9, 0.5]


def test_key_does_not_match_inside_longer_names():
    assert metrics.key_occurrences("val_loss: 0.2", "loss") == []


def test_regex_uses_named_or_first_group():
    assert [o.value for o in metrics.regex_occurrences(LOG, r"val_acc: (\S+)")] == [0.81, 0.86]
    assert [o.value for o in metrics.regex_occurrences(LOG, r"loss=(?P<value>[\d.]+)")] == [
        0.9,
        0.5,
    ]
    with pytest.raises(ValueError):
        metrics.regex_occurrences(LOG, r"val_acc")


def test_json_pointer_scalar_and_list():
    doc = '{"test": {"acc": 0.9, "history": [0.5, 0.7, true]}}'
    assert metrics.json_pointer_occurrences(doc, "/test/acc")[0].value == 0.9
    assert [o.value for o in metrics.json_pointer_occurrences(doc, "/test/history")] == [0.5, 0.7]
    with pytest.raises(metrics.ExtractionError):
        metrics.json_pointer_occurrences(doc, "/test/missing")


def test_csv_column_rows():
    found = metrics.csv_occurrences("epoch,acc\n1,0.5\n2,n/a\n3,0.75\n", "acc")
    assert [(o.value, o.row) for o in found] == [(0.5, 1), (0.75, 3)]


@pytest.mark.parametrize(
    ("how", "value"),
    [("last", 0.86), ("first", 0.81), ("max", 0.86), ("min", 0.81), ("mean", 0.835)],
)
def test_reduce(how, value):
    occurrences = metrics.regex_occurrences(LOG, r"val_acc: (\S+)")
    reduced, used = metrics.reduce_occurrences(occurrences, how)
    assert reduced == pytest.approx(value)
    assert used


def test_reduce_without_matches_fails():
    with pytest.raises(metrics.ExtractionError):
        metrics.reduce_occurrences([], "last")
