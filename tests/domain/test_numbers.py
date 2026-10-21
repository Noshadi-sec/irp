import pytest

from irp.domain.numbers import find_numbers, is_power_of_ten, numbers_match, parse_number


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("94.1%", 94.1, "%"),
        ("$94.1\\%$", 94.1, "%"),
        ("2.0x", 2.0, "x"),
        ("2.1\u00d7", 2.1, "x"),
        ("\u22120.31", -0.31, None),
        ("1,234.5 ms", 1234.5, "ms"),
        ("1e-3", 0.001, None),
        ("\\textbf{93.8}", 93.8, None),
        ("93.8 ± 0.2", 93.8, None),
    ],
)
def test_parse_number_reads_paper_formats(text, value, unit):
    parsed = parse_number(text)
    assert parsed.value == pytest.approx(value)
    assert parsed.unit == unit


def test_parse_number_without_digits_fails():
    with pytest.raises(ValueError):
        parse_number("n/a")


def test_find_numbers_skips_identifiers():
    values = [v for v, _s, _e in find_numbers("conv3 layer v2: loss=0.31 acc: 93.8% lr 1e-3")]
    assert values == [0.31, 93.8, 0.001]


def test_numbers_match_uses_printed_precision():
    assert numbers_match("94.1%", 94.12)
    assert not numbers_match("94.1%", 94.16)


@pytest.mark.parametrize(
    ("value", "ok"), [(100, True), (0.01, True), (1, True), (3, False), (0, False), (1e7, False)]
)
def test_power_of_ten(value, ok):
    assert is_power_of_ten(value) is ok
