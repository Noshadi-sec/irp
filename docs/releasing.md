# Releasing IRP

Pushes to main open or refresh a Release Please PR with the next version and
changelog. Every release bumps the minor version (0.1.0, 0.2.0, ...); mark breaking
changes with `!` and migration notes. Review the PR, wait
for CI, and merge it to publish.

## What the release workflow does

On the merge of the release PR, `release.yml`:

1. **Release Please** creates the tag `irp-X.Y.Z` and the GitHub release.
2. **Qualification** runs the full CI workflow at the exact released commit.
3. **Build and attest** builds the sdist and wheel once, checks they carry the
   released version, rehearses the exact wheel with `scripts/verify_package.py`
   in an empty environment, and creates build-provenance attestations.
4. **Publish to PyPI** uploads those same files through trusted publishing
   (no API token), with PyPI attestations.
5. **Verify the published package** installs `irp-agents==X.Y.Z` from PyPI with
   uvx, retrying while the index propagates.
6. **Publish to the MCP Registry** validates `server.json` and publishes it
   with GitHub OIDC, using a pinned, checksummed `mcp-publisher`.

Ordinary pushes to main never publish packages.

## One-time setup

- **PyPI trusted publisher.** On PyPI, add a (pending) publisher for project
  `irp`: owner `Noshadi-sec`, repository `irp`, workflow `release.yml`,
  environment `pypi`. Create the `pypi` environment in the repository settings,
  and require reviewers on it if you want a manual gate.
- **Release Please token.** Optionally add `RELEASE_PLEASE_TOKEN`, a
  fine-grained token with contents and pull-request write access, so release
  PRs start CI automatically.
- **MCP Registry.** The server name `io.github.Noshadi-sec/irp` is verified
  through GitHub OIDC; the README's `mcp-name:` line proves PyPI ownership.

## Version files

Release Please updates `src/irp/_version.py`, `server.json` (both
versions), the pinned examples in `docs/installation.md` and
`docs/client-configuration.md`, `CHANGELOG.md` and the manifest.
`scripts/check_release_metadata.py` (run in CI) fails when any of them disagree.

## Recovering a partial publication

Re-run failed jobs in the original run; publishing jobs reuse the built
artifact. Never retag or republish a version to fix release notes: edit the
GitHub release text instead. A broken release is fixed by a new release.
