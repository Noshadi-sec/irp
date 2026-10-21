"""Read, plan and apply one client's MCP registration.

Edits are additive: unrelated servers and settings stay as they are. Every
change makes a backup first (the first snapshot is kept forever as
`<file>.irp.backup`; a later, different file gets a separate recovery copy),
writes atomically, reads the result back, and restores the backup if the
readback does not match. A malformed file blocks setup instead of being rewritten.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from irp.application.clients import AgentClient
from irp.application.registration import RegistrationState, classify, entry_for, is_owned
from irp.domain.canonical import sha256_bytes
from irp.filesystem import atomic_write_bytes
from irp.identity import PRODUCT

KEY = PRODUCT.mcp_server_key


@dataclass(frozen=True)
class ConfigSnapshot:
    client: AgentClient
    exists: bool
    raw: bytes
    document: Any  # dict for JSON, tomlkit document for TOML, None when unreadable
    error: str | None

    @property
    def digest(self) -> str:
        return sha256_bytes(self.raw)

    def entry(self) -> Any:
        if self.document is None:
            return None
        servers = self.document.get(self.client.servers_key)
        if servers is None:
            return None
        value = servers.get(KEY)
        return _plain(value)


def _plain(value: Any) -> Any:
    """tomlkit items to plain Python for comparison."""
    if hasattr(value, "unwrap"):
        return value.unwrap()
    return value


def read_snapshot(client: AgentClient) -> ConfigSnapshot:
    path = client.config_path
    if path.is_symlink() and not path.exists():
        return ConfigSnapshot(client, False, b"", None, f"{path} is a broken symbolic link.")
    if not path.exists():
        empty: Any = {} if client.format == "json" else tomlkit.document()
        return ConfigSnapshot(client, False, b"", empty, None)
    if not path.is_file():
        return ConfigSnapshot(client, True, b"", None, f"{path} is not a regular file.")
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict") if raw else ""
    try:
        if client.format == "json":
            document = json.loads(text) if text.strip() else {}
            if not isinstance(document, dict):
                return ConfigSnapshot(
                    client, True, raw, None, f"{path} does not hold a JSON object."
                )
            servers = document.get(client.servers_key)
            if servers is not None and not isinstance(servers, dict):
                return ConfigSnapshot(
                    client, True, raw, None, f"{client.servers_key} in {path} is not an object."
                )
        else:
            document = tomlkit.parse(text)
            servers = document.get(client.servers_key)
            if servers is not None and not isinstance(servers, dict):
                return ConfigSnapshot(
                    client, True, raw, None, f"{client.servers_key} in {path} is not a table."
                )
    except (json.JSONDecodeError, TOMLKitError, UnicodeDecodeError) as exc:
        return ConfigSnapshot(client, True, raw, None, f"{path} could not be parsed: {exc}")
    return ConfigSnapshot(client, True, raw, document, None)


@dataclass(frozen=True)
class Inspection:
    state: RegistrationState
    operation: str | None  # "create", "update" or None when already current or blocked
    blocker: str | None
    backup_path: Path | None
    entry: Any


def backup_paths(path: Path, raw: bytes) -> tuple[Path, Path | None]:
    """The retained first snapshot, and a recovery copy when the file differs from it."""
    first = path.with_name(path.name + ".irp.backup")
    if first.exists() and first.read_bytes() != raw:
        return first, path.with_name(f"{path.name}.irp.backup.{sha256_bytes(raw)[7:19]}.recovery")
    return first, None


def inspect_registration(client: AgentClient, command: list[str]) -> Inspection:
    snapshot = read_snapshot(client)
    if snapshot.error is not None:
        return Inspection(
            "invalid",
            None,
            f"{snapshot.error} Repair or remove it, then rerun setup; IRP will not overwrite it.",
            None,
            None,
        )
    entry = snapshot.entry()
    state = classify(entry, command)
    if state == "unowned":
        return Inspection(
            state,
            None,
            f"{client.config_path} already has a '{KEY}' server that IRP did not write. Rename or "
            "remove it yourself, then rerun setup.",
            None,
            entry,
        )
    if state == "invalid":
        return Inspection(
            state, None, f"The '{KEY}' entry in {client.config_path} is malformed.", None, entry
        )
    desired = entry_for(command, entry, codex=client.id == "codex")
    if state == "aligned" and _comparable(entry) == _comparable(desired):
        return Inspection(state, None, None, None, entry)
    first, recovery = (
        backup_paths(client.config_path, snapshot.raw) if snapshot.exists else (None, None)
    )
    return Inspection(
        state,
        "update" if snapshot.exists else "create",
        None,
        recovery or first,
        entry,
    )


def _comparable(entry: Any) -> Any:
    return json.loads(json.dumps(entry, sort_keys=True, default=str)) if entry is not None else None


def _render(client: AgentClient, document: Any) -> bytes:
    if client.format == "json":
        return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return tomlkit.dumps(document).encode("utf-8")


def _with_entry(client: AgentClient, document: Any, entry: dict[str, Any] | None) -> Any:
    """Return the document with IRP's entry set (or removed when entry is None)."""
    if client.format == "json":
        updated = dict(document)
        servers = dict(updated.get(client.servers_key) or {})
        if entry is None:
            servers.pop(KEY, None)
        else:
            servers[KEY] = entry
        updated[client.servers_key] = servers
        return updated
    if client.servers_key not in document:
        document[client.servers_key] = tomlkit.table(is_super_table=True)
    servers = document[client.servers_key]
    if entry is None:
        if KEY in servers:
            del servers[KEY]
        return document
    table = tomlkit.table()
    for key, value in entry.items():
        if isinstance(value, dict):
            inline = tomlkit.inline_table()
            inline.update(value)
            table[key] = inline
        else:
            table[key] = value
    servers[KEY] = table
    return document


class ConfigWriteError(Exception):
    def __init__(self, message: str, backup: Path | None = None) -> None:
        super().__init__(message)
        self.backup = backup


def _publish(client: AgentClient, snapshot: ConfigSnapshot, new_bytes: bytes) -> Path | None:
    """Back up, refuse a concurrent change, write atomically. Returns the backup path."""
    path = client.config_path
    backup: Path | None = None
    if snapshot.exists:
        first, recovery = backup_paths(path, snapshot.raw)
        if not first.exists():
            atomic_write_bytes(first, snapshot.raw)
            backup = first
        elif recovery is not None:
            atomic_write_bytes(recovery, snapshot.raw)
            backup = recovery
        else:
            backup = first
        current = path.read_bytes() if path.exists() else b""
        if current != snapshot.raw:
            raise ConfigWriteError(
                f"{path} changed while setup was running; nothing was written. "
                + (client.note or "Close the client and retry."),
                backup,
            )
    elif path.exists():
        raise ConfigWriteError(f"{path} appeared while setup was running; nothing was written.")
    atomic_write_bytes(path, new_bytes)
    return backup


def apply_registration(client: AgentClient, command: list[str]) -> dict[str, Any]:
    snapshot = read_snapshot(client)
    if snapshot.error is not None:
        return {"status": "failed", "detail": snapshot.error}
    entry = snapshot.entry()
    if entry is not None and not is_owned(entry):
        return {
            "status": "failed",
            "detail": f"An unowned '{KEY}' entry exists in {client.config_path}.",
        }
    desired = entry_for(command, entry, codex=client.id == "codex")
    if classify(entry, command) == "aligned" and _comparable(entry) == _comparable(desired):
        return {"status": "unchanged"}
    document = _with_entry(client, snapshot.document, desired)
    try:
        backup = _publish(client, snapshot, _render(client, document))
    except ConfigWriteError as exc:
        return {
            "status": "failed",
            "detail": str(exc),
            "backup_path": str(exc.backup) if exc.backup else None,
        }
    readback = read_snapshot(client)
    if readback.error is not None or _comparable(readback.entry()) != _comparable(desired):
        if backup is not None:
            atomic_write_bytes(client.config_path, snapshot.raw)
        return {
            "status": "failed",
            "detail": "The written configuration did not read back as expected; the previous file was restored.",
            "backup_path": str(backup) if backup else None,
        }
    return {"status": "configured", "backup_path": str(backup) if backup else None}


def remove_registration(client: AgentClient) -> dict[str, Any]:
    snapshot = read_snapshot(client)
    if not snapshot.exists:
        return {"status": "absent"}
    if snapshot.error is not None:
        return {"status": "failed", "detail": snapshot.error}
    entry = snapshot.entry()
    if entry is None:
        return {"status": "absent"}
    if not is_owned(entry):
        return {"status": "kept", "detail": f"The '{KEY}' entry was not written by IRP."}
    document = _with_entry(client, snapshot.document, None)
    try:
        backup = _publish(client, snapshot, _render(client, document))
    except ConfigWriteError as exc:
        return {"status": "failed", "detail": str(exc)}
    return {"status": "removed", "backup_path": str(backup) if backup else None}
