# Connection and recovery

Read this only for an observed blocker. Keep the person's paper and question in
view, explain what stopped you, and resume after the repair.

## Choose the remedy from what you observed

| Observation | Meaning and next step |
| --- | --- |
| No IRP tools in the session | Check registration: `irp doctor --client claude_code --json` (or `codex`, `cursor`). Installing the skill alone does not register MCP. |
| Missing or stale registration | Plan a repair: `irp setup --client <id> --dry-run --json`. Show the exact paths, backups and skill change; apply with `--yes` only after approval. |
| Registration aligned, tools still absent | Restart or reconnect the agent. Doctor reads files; it cannot see the live session. |
| `provider_unavailable` (uv, Docker, Modal) | Follow the error's remediation. IRP never installs uv, Docker or Python; ask the person. |
| `rule_violation` | A hard rule refused the action; `details.rule` names it. Change the approach, not the rule. |
| `needs_confirmation` from `run_remote` | Show the person the estimate in `details` and ask. |
| `verification_failed` | A recorded file or the log changed. Run `irp verify` and tell the person; never edit evidence. |
| Client timed out waiting for `run` | The run may still be going. Call `run_status` before starting anything; use `wait: false` next time. |

When `irp` is not on PATH, `uvx irp-agents@latest <command>` runs the
published package without installing it.

## Timeouts

A client timeout ("timed out awaiting tools/call") means the client stopped
waiting, not that the run stopped. IRP keeps one run per study and marks a
run lost only when its owner process stops beating. Codex reads
`tool_timeout_sec` (seconds) from its `[mcp_servers.irp]` table; setup
writes 1800.

## Manual registration

For other MCP clients, register a stdio server:

```json
{ "mcpServers": { "irp": { "command": "uvx", "args": ["irp-agents@latest", "mcp"] } } }
```

Pin an exact version for persistent registrations.
