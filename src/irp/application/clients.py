"""Supported agent clients: where each keeps its MCP registrations and personal skills.

Claude Code, Codex and Cursor are configured by setup. Any other MCP client can
register the server by hand (see docs/installation.md#manual-registration).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ClientFormat = Literal["json", "toml"]


@dataclass(frozen=True)
class AgentClient:
    id: str
    display_name: str
    config_path: Path
    marker_path: Path
    format: ClientFormat
    servers_key: str
    skill_root: Path
    note: str | None = None

    @property
    def detected(self) -> bool:
        return self.marker_path.exists() or self.config_path.exists()


SUPPORTED_CLIENT_IDS = ("claude_code", "codex", "cursor")


def shared_skill_root(home: Path) -> Path:
    return home / ".agents" / "skills"


def supported_clients(home: Path, env: Mapping[str, str]) -> list[AgentClient]:
    """Resolve every client location the same way setup, doctor and uninstall do."""
    # An empty override is treated as unset, as the clients themselves do.
    claude_dir = Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else None
    codex_dir = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home / ".codex"
    return [
        AgentClient(
            id="claude_code",
            display_name="Claude Code",
            config_path=(claude_dir or home) / ".claude.json",
            marker_path=claude_dir or home / ".claude",
            format="json",
            servers_key="mcpServers",
            skill_root=(claude_dir or home / ".claude") / "skills",
            note="Claude Code rewrites this file while it runs; if setup reports a concurrent change, "
            "close Claude Code sessions and retry.",
        ),
        AgentClient(
            id="codex",
            display_name="Codex",
            config_path=codex_dir / "config.toml",
            marker_path=codex_dir,
            format="toml",
            servers_key="mcp_servers",
            skill_root=shared_skill_root(home),
        ),
        AgentClient(
            id="cursor",
            display_name="Cursor",
            config_path=home / ".cursor" / "mcp.json",
            marker_path=home / ".cursor",
            format="json",
            servers_key="mcpServers",
            skill_root=shared_skill_root(home),
        ),
    ]
