# Installation and setup

Run IRP, connect your agents, and check the tools a paper needs. Setup
previews every change and asks for approval before applying it.

| Task | Section |
| --- | --- |
| Connect an agent | [Start setup](#start-setup), then [review changes](#review-setup-changes) |
| Check one task's readiness | [Readiness](#check-readiness) |
| Update or remove IRP | [Maintenance](#update-and-remove) |
| Use another MCP client | [Manual registration](#manual-registration) |
| Resolve a client-specific problem | [Client configuration](client-configuration.md) |

## Requirements

- macOS or Linux, Python 3.11+ (uv provides it when missing).
- [uv](https://docs.astral.sh/uv/) for `uvx irp-agents`, `uv tool install` and the default environment backend.
- git, so each run is tied to a code commit.
- Optional: Docker for isolated runs; an NVIDIA GPU or a paid GPU provider for GPU papers.

IRP never installs or upgrades uv, Python, git, Docker or CUDA.

## Start setup

```bash
uvx irp-agents setup
```

Choose the agents to configure, review the proposed paths and changes, and
approve. Restart the agents named in the completion message.

For the latest release explicitly, use `uvx irp-agents@latest setup`.

## Review setup changes

Setup first lists the supported agents. Existing IRP registrations are
selected by default. Newly detected agents are offered but not selected:
detection gives setup context, not permission. Explicit `--client` flags skip
the question.

The plan lists each configuration file it will create or update, the backup it
will keep, the exact command agents will launch, and each skill destination.
Nothing is written until you approve. Declining or pressing Ctrl-C changes
nothing.

Configuration writes:

- keep every unrelated setting, server and comment (Codex TOML comments survive);
- keep your own `env` values and Codex timeouts on an existing IRP entry;
- back up the file first: the first snapshot stays as `<file>.irp.backup`;
  a later, different file gets `<file>.irp.backup.<hash>.recovery`;
- write atomically, read the result back, and restore the backup if it does not match;
- refuse a file that changed while setup ran, a malformed file, or a `irp`
  entry that IRP did not write.

For scripts, select clients explicitly:

```bash
irp setup --client claude_code --client codex --dry-run --json
irp setup --client claude_code --client codex --yes
```

`--dry-run` returns the plan with status `planned` and exit code 0. `--yes`
without `--client` or `--all-detected` only refreshes existing IRP
registrations; it never adds new ones. Without approval, a non-interactive run
returns `needs_confirmation` and exit code 1. `--no-skill` skips the skill.

### What setup writes

| Client | Configuration | Entry | Skill destination |
| --- | --- | --- | --- |
| Claude Code | `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`) | `mcpServers.irp` | `~/.claude/skills/reproduce-paper` (or `$CLAUDE_CONFIG_DIR/skills/...`) |
| Codex | `~/.codex/config.toml` (or `$CODEX_HOME/config.toml`) | `[mcp_servers.irp]` with `startup_timeout_sec = 30`, `tool_timeout_sec = 1800` | `~/.agents/skills/reproduce-paper` |
| Cursor | `~/.cursor/mcp.json` | `mcpServers.irp` | `~/.agents/skills/reproduce-paper` |

The registered command is pinned:

<!-- x-release-please-start-version -->

- from `uvx`: `uvx irp-agents@0.7.0 mcp`
- from an installed IRP: the installation's own Python, `-m irp mcp`

<!-- x-release-please-end -->

Setup never registers a path inside uv's temporary cache.

Installed skills carry `.irp-skill.json`, an ownership manifest. Setup only
replaces copies it owns; a directory named `reproduce-paper` without the
manifest is left alone and blocks setup until you move it or pass `--no-skill`.

## Limit IRP to one Claude Code profile or project

Setup registers IRP for the whole client. To keep it in a separate Claude
Code profile, set `CLAUDE_CONFIG_DIR` for setup and for Claude Code:

```bash
CLAUDE_CONFIG_DIR=~/.claude-papers uvx irp-agents setup --client claude_code
CLAUDE_CONFIG_DIR=~/.claude-papers claude
```

For one project only, skip setup for Claude Code and register at local scope
from the project directory:

<!-- x-release-please-start-version -->

```bash
claude mcp add --scope local irp -- uvx irp-agents@0.7.0 mcp
```

<!-- x-release-please-end -->

`irp doctor` and `irp uninstall` read only user-level entries, so they
do not report or remove a local-scope registration.

## Check readiness

```bash
irp doctor
```

Doctor is strictly read-only. Without options it audits Python, uv, git,
Docker, GPUs, disk space, PDF parsers, Modal, every detected agent registration
and the installed skill; `healthy` can be false while your workflow still works
(Docker is optional, for example). Scope it to what you need:

| Need | Command |
| --- | --- |
| One agent's registration | `irp doctor --client codex --json` |
| The installed skill | `irp doctor --skill --json` |

A scoped report sets `scope.mode` to `explicit`; only its `scope_checks` decide
`healthy` and the exit status. Doctor checks files; it cannot see whether a
running agent has loaded the server. Restart the agent after a change.

## Update and remove

```bash
irp update
```

`update` upgrades the installation that owns the running command: a uv tool
(`uv tool install --force irp-agents==<latest>`), a pipx install, or a virtual
environment. It verifies the new version before reporting success, then tells
you to run `irp setup` to refresh registrations pinned to the old version.
uvx needs no update; use `uvx irp-agents@latest setup`. A source checkout updates
with git.

```bash
irp uninstall
```

`uninstall` removes only IRP-owned registrations and skill copies, with
backups, after showing its plan. It never touches studies, evidence logs or
reports.

## Install options

| Route | Command |
| --- | --- |
| One-off, no install | `uvx irp-agents <command>` |
| Installed command | `uv tool install irp-agents`, then `irp --help` |
| Installer script | `curl -fsSL https://raw.githubusercontent.com/Noshadi-sec/irp/main/install.sh \| bash` |

The installer prints the version, command and destination before installing
with `uv tool install`, verifies the installed version, and starts setup when a
terminal is available. Options: `--version X.Y.Z`, `--dry-run`, `--no-setup`,
`--verbose`. It requires uv and installs nothing else.

## Manual registration

For any other MCP client, register a stdio server:

<!-- x-release-please-start-version -->

```json
{
  "mcpServers": {
    "irp": {
      "command": "uvx",
      "args": ["irp-agents@0.7.0", "mcp"]
    }
  }
}
```

<!-- x-release-please-end -->

Persistent registrations should pin one exact version. To install only the
skill, run `uvx irp-agents setup --skill --yes` without `--client`; it goes to
`~/.agents/skills/reproduce-paper`. You can also copy
`.agents/skills/reproduce-paper` from the repository.

IRP is also published in the official MCP Registry as
`io.github.Noshadi-sec/irp`, pointing at the same PyPI package.

## Supported agents

| Client | `--client` value |
| --- | --- |
| Claude Code | `claude_code` |
| Codex | `codex` |
| Cursor | `cursor` |
