<!--
PR title: type(optional-scope): imperative outcome
The title becomes the squash-merge commit subject and the changelog entry.
-->

## Summary

<!-- What problem does this solve for a person, an agent or a maintainer? Link "Fixes #123". -->

## Problem and expected behavior

<!-- For fixes, the smallest trigger and the broken invariant. For features, the use case. -->

## Change and scope

<!-- The approach, why it fits IRP's architecture, and what is intentionally left out.
Follow the contribution scope; new compute providers, paid compute and code execution
outside the study need a linked maintainer scope decision. -->

## Contract and evidence impact

<!-- Short answers are welcome. Write "unknown" for anything not established. -->

- Tool contracts, CLI or MCP schema:
- Evidence log, report or verify:
- Hard rules (which rule, and is it still enforced):
- Agent configuration, setup or skill:

Effects (check known effects):

- [ ] Reads the paper or study only.
- [ ] Runs code.
- [ ] Contacts network services.
- [ ] Spends money (paid compute).
- [ ] Changes agent configuration.
- [ ] Documentation only.

## Evidence and regression coverage

<!-- Executed, source-derived or proposed? For fixes, show the original failure. -->

- Tests added or updated:
- Representative CLI/MCP output (if user-visible):
- Remaining gaps:

## Validation performed

<!-- Only commands that actually ran, with their results. -->

- `command` — result

## Author readiness

<!-- The human owner completes these before requesting review. AI agents must leave
them for a human. Draft PRs may leave them unchecked. -->

Human owner: <!-- @GitHub-handle -->

- [ ] I reviewed the final diff and relevant existing code, understand the change and its edge cases, and take responsibility for the complete PR, including AI-assisted work.
- [ ] I checked the evidence above, confirmed it supports the current change, and recorded meaningful validation gaps.
- [ ] I declare this PR ready for initial maintainer review.

## Before merge

- [ ] One focused outcome; the title follows `type(scope): outcome`.
- [ ] Tests cover the changed behavior and its failure paths; every hard rule keeps its refusal test.
- [ ] Docs, contracts and the generated catalog are updated where needed.
- [ ] No secrets, papers, study data or unrelated changes in the diff.
