# Client configuration

Use this reference when a client's paths, profiles or timeouts affect IRP.
Start with [installation and setup](installation.md).

## Claude Code

Setup writes `mcpServers.irp` into `~/.claude.json` and the skill into
`~/.claude/skills/reproduce-paper`. With `CLAUDE_CONFIG_DIR` set (and not empty),
both move under that directory.

Claude Code rewrites `~/.claude.json` while it runs. If setup reports that the
file changed during setup, close Claude Code sessions and rerun setup; nothing
was written.

Claude Code waits for long tool calls, but prefer `run` with `wait: false` and
`run_status` for runs longer than a few minutes.

## Codex

Setup writes a table to `~/.codex/config.toml` (or `$CODEX_HOME/config.toml`):

<!-- x-release-please-start-version -->

```toml
[mcp_servers.irp]
command = "uvx"
args = ["irp-agents@0.5.0", "mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 1800
```

<!-- x-release-please-end -->

Comments and other tables are preserved. Setup keeps your own
`startup_timeout_sec`, `tool_timeout_sec` and `env` on an existing entry.
`tool_timeout_sec` is in seconds; it is how long Codex waits for one tool call,
not how long a run may take. Codex can require approval for tool calls under its
own policy; that is separate from IRP.

The skill goes to `~/.agents/skills/reproduce-paper`.

## Cursor

Setup writes `mcpServers.irp` into `~/.cursor/mcp.json`. The file must be
plain JSON; setup refuses files with comments rather than rewriting them. The
skill goes to `~/.agents/skills/reproduce-paper`.

## Environment overrides

Add variables to the entry's `env` object; setup preserves them.

| Variable | Effect |
| --- | --- |
| `IRP_LOG_LEVEL` | stderr logging (`info` by default for MCP) |
| `IRP_UV` | Path to uv when it is not on the client's `PATH` |
| `IRP_DOCKER` | Path to docker when it is not on the client's `PATH` |
| `DOCKER_HOST` / `DOCKER_CONFIG` | Passed through to Docker as usual |

GUI clients often start with a minimal `PATH`. If doctor passes in a terminal
but tools report `provider_unavailable` for uv or Docker, set `IRP_UV` or
`IRP_DOCKER` in the entry's `env`.
