"""Canonical JSON and digests: the byte-level identity of every evidence record."""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_HASH = "sha256:" + "0" * 64


def canonical_json(value: Any) -> str:
    """Serialize with sorted keys, no whitespace and no NaN, so equal data hashes equally."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_value(value: Any) -> str:
    return sha256_text(canonical_json(value))
