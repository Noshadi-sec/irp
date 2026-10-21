"""Append-only access to evidence.jsonl, shared safely by CLI, MCP and background runners."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from irp.domain.errors import ErrorCode, IRPError
from irp.domain.evidence import ChainReport, EvidenceRecord, parse_and_verify, seal_record
from irp.filesystem import file_lock
from irp.identity import PRODUCT


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EvidenceLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")

    def read(self) -> ChainReport:
        text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        return parse_and_verify(text)

    def read_verified(self) -> list[EvidenceRecord]:
        """Records of an intact log; a broken chain stops every workflow that depends on it."""
        report = self.read()
        if not report.ok:
            raise IRPError(
                ErrorCode.VERIFICATION_FAILED,
                "The evidence log fails verification, so the study cannot be trusted or extended.",
                remediation="Run `irp verify` to see each problem. Restore evidence.jsonl from a "
                "backup or git history; IRP never repairs a log.",
                details={"problems": report.problems[:20]},
            )
        return report.records

    def append(self, record_type: str, data: dict[str, Any], *, actor: str) -> EvidenceRecord:
        """Seal and append one record under the study lock; refuses to extend a broken chain."""
        with file_lock(self.lock_path):
            records = self.read_verified()
            record = seal_record(
                seq=len(records),
                ts=utc_now(),
                type=record_type,
                actor=actor,
                tool_version=PRODUCT.version,
                data=data,
                prev=records[-1].hash if records else "sha256:" + "0" * 64,
            )
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(record.to_json_line())
                handle.flush()
                os.fsync(handle.fileno())
            return record
