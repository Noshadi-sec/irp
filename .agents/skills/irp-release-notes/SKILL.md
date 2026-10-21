---
name: irp-release-notes
description: Prepare or rewrite IRP release notes from git history before merging a Release Please PR.
---

# IRP release notes

Read [docs/releasing.md](../../../docs/releasing.md) first. This skill prepares
notes; it does not authorize merging, tagging or publishing.

1. Find the previous tag (`irp-X.Y.Z`) and list the commits and merged PRs
   since then: `git log --oneline irp-PREVIOUS..origin/main`.
2. Read ambiguous PRs and diffs before describing them. Never describe work that
   was reverted.
3. Rewrite only the newest section of `CHANGELOG.md` under `### Highlights`,
   `### Changes`, `### Fixes` and, when present, `### ⚠ BREAKING CHANGES` with
   migration steps. Write for people who use IRP: describe the resulting
   behavior, not the implementation.
4. Credit each human contributor once, with the PR link and `Thanks @handle`.
   Never guess a handle; exclude bots and agent accounts.
5. Update the Release Please PR body to match, keeping its header and footer.

Distinguish verified provider behavior (uv, Docker, Modal lanes that actually
ran) from simulated checks. Never retag or republish to fix notes.
