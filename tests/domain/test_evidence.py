import json

import pytest

from irp.domain.canonical import GENESIS_HASH
from irp.domain.evidence import parse_and_verify, seal_record


def chain(count: int) -> str:
    lines, prev = [], GENESIS_HASH
    for seq in range(count):
        record = seal_record(
            seq=seq,
            ts="2026-01-01T00:00:00.000Z",
            type="note.added",
            actor="cli",
            tool_version="0.1.0",
            data={"note": {"id": f"n{seq + 1}", "n": seq}},
            prev=prev,
        )
        lines.append(record.to_json_line())
        prev = record.hash
    return "".join(lines)


def test_intact_chain_verifies_and_reports_head():
    report = parse_and_verify(chain(5))
    assert report.ok
    assert len(report.records) == 5
    assert report.head == report.records[-1].hash


def test_empty_log_is_valid_with_genesis_head():
    report = parse_and_verify("")
    assert report.ok and report.head == GENESIS_HASH


def test_editing_data_breaks_that_record_hash():
    lines = chain(3).splitlines()
    record = json.loads(lines[1])
    record["data"]["note"]["n"] = 99
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    report = parse_and_verify("\n".join(lines) + "\n")
    assert [p["kind"] for p in report.problems] == ["hash_mismatch"]
    assert report.problems[0]["line"] == 2


def test_rehashing_an_edit_still_breaks_the_next_link():
    lines = chain(3).splitlines()
    record = json.loads(lines[1])
    record["data"]["note"]["n"] = 99
    body = {k: v for k, v in record.items() if k != "hash"}
    from irp.domain.canonical import digest_value

    record["hash"] = digest_value(body)
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    report = parse_and_verify("\n".join(lines) + "\n")
    assert [p["kind"] for p in report.problems] == ["broken_link"]
    assert report.problems[0]["line"] == 3


def test_deleting_or_reordering_records_is_detected():
    lines = chain(4).splitlines()
    deleted = parse_and_verify("\n".join(lines[:1] + lines[2:]) + "\n")
    assert {"sequence_gap", "broken_link"} <= {p["kind"] for p in deleted.problems}
    swapped = parse_and_verify("\n".join([lines[0], lines[2], lines[1], lines[3]]) + "\n")
    assert not swapped.ok


def test_truncated_last_line_and_garbage_are_reported():
    text = chain(2)
    assert parse_and_verify(text[:-1]).problems[-1]["kind"] == "unterminated_line"
    garbage = parse_and_verify(text + "{not json\n")
    assert garbage.problems[-1]["kind"] == "malformed_json"


def test_unknown_types_and_nan_are_refused_at_sealing():
    with pytest.raises(ValueError):
        seal_record(
            seq=0, ts="t", type="made.up", actor="cli", tool_version="0", data={}, prev=GENESIS_HASH
        )
    with pytest.raises(ValueError):
        seal_record(
            seq=0,
            ts="t",
            type="note.added",
            actor="cli",
            tool_version="0",
            data={"x": float("nan")},
            prev=GENESIS_HASH,
        )
