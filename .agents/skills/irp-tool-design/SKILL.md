---
name: irp-tool-design
description: Design or change IRP tools, CLI/MCP contracts, evidence record types, hard-rule enforcement and report fields.
---

# IRP tool design

Use the [tool design guide](../../../docs/tool-design.md) for boundaries,
contracts and evidence semantics. Inspect the current contracts
(`src/irp/contracts/`), the nearest existing tool, and how
`src/irp/domain/state.py` replays its records before proposing a change.

For a design request, return: the agent question the tool answers, the input
model, the evidence record it writes, the hard rules it enforces and how it
refuses, what `verify` and the report gain, and the nearest alternative.

For an implementation:

1. Change the input model and `ToolContract`, then the handler and its
   `operations.HANDLERS` binding, then the CLI command.
2. Regenerate the catalog: `uv run python scripts/generate_catalog.py`.
3. Add tests through `execute`, the CLI and MCP adapters, and a refusal test for
   every rule the change touches. Never delete an existing refusal test.
4. Update the skill and docs that describe the behavior.

Consult [testing](../../../docs/testing.md) for lanes and
[contributing](../../../CONTRIBUTING.md) for scope, especially for anything
that runs code, spends money or edits agent configuration.
