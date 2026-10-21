# Guided MCP prompts

IRP exposes two workflows through the MCP `prompts` capability. They
suggest a path through the tools; they never call tools themselves, and agents
can skip suggestions that do not fit.

| Prompt | Arguments | Purpose |
| --- | --- | --- |
| `build_paper` | `paper`, `study`, optional `claims` | The full workflow for one paper: claims first, faithful runs, verdicts, report |
| `resume_study` | `study` | Pick up an existing study from `study_status` |

Arguments are rendered as data, not instructions, so a paper title or path
cannot redirect the agent.

```json
{ "method": "prompts/get", "params": { "name": "build_paper", "arguments": { "paper": "2501.12345", "study": "/home/me/studies/x", "claims": "Table 2" } } }
```

The [skill](../.agents/skills/reproduce-paper/SKILL.md) carries the same
workflow with the hard rules and on-demand guides; clients that support skills
should prefer it.
