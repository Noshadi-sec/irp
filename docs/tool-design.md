# Tool design

## Decide whether to add a tool

Start from the agent's question at a step of the workflow (intake, claims,
plan, build, run, measure, judge, report). Inspect the catalog and the nearest
existing tool first. Extend a tool when its intent and result match; add one
for a distinct outcome or a different effect (reading, writing evidence,
running code, spending money).

## Keep the evidence honest

Every tool that changes a study appends exactly one evidence record whose
`data` holds the facts a report needs, never prose. Before adding a tool, decide:

- which record type it writes, and how `domain/state.py` replays it;
- which hard rule it touches, and how it refuses with `rule_violation(n, ...)`;
- which files it vouches for, with hashes, and how `verify` rechecks them;
- what the report shows, and what the completion gate requires.

A number that can reach a verdict must come from a run's own output, checked by
hash. Agents can always run ordinary commands; a tool exists to make an action
recorded and checkable, not to replace the shell.

## Define the contract

- One pydantic model in `contracts/inputs.py` with a description on every
  field; strict (`extra="forbid"`); explicit study identity.
- One `ToolContract` in `contracts/catalog.py` with stage, summary,
  description, effects and annotations.
- One handler in `application/` bound by name in `application/operations.py`.
- One CLI command in `cli/app.py` that builds the same input.
- Regenerate `docs/mcp-contracts.md` with `scripts/generate_catalog.py`.

Return the requested facts inline, compactly: ids, the recorded facts, and the
next step when it is not obvious. Page long text. Report partial results and
limitations; missing coverage is unknown, not absent.

## Own side effects

Workflows that run code or touch configuration must state their effects,
bound their time, clean up what they own, and leave everything else alone.
Runs belong to one owner at a time (the foreground process or the detached
runner); ownership is visible through the heartbeat. Installers never install
unrelated software.

## Evaluate

Cover the success path, malformed input, each refusal, cancellation or timeout
where it exists, and the CLI and MCP adapters. Provider claims need the
matching real-provider lane (uv, Docker, Modal); a simulated provider does not
establish real behavior. When a change affects what agents see, compare token
usage and steps on a representative study before and after.
