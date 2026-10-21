# Security Policy

## Supported versions

Security fixes are provided for the latest published version of IRP.
Upgrade to the latest release before reporting a problem that may already be
fixed.

## Reporting a vulnerability

Do not disclose vulnerabilities, proof-of-concept exploits, credentials or
private study data in a public issue.

Use **Report a vulnerability** in the repository's **Security** tab to submit the
report privately. Include the affected IRP version, operating system,
Python version, the tool or command involved, impact, reproduction conditions,
and any suggested mitigation. Remove credentials, API tokens and unrelated local
paths from logs.

The maintainers will acknowledge the report, assess its scope, and coordinate
remediation and disclosure timing with you.

## Official sources

Get IRP only from [Noshadi-sec/irp](https://github.com/Noshadi-sec/irp) and
the [irp-agents package on PyPI](https://pypi.org/project/irp-agents/). Releases are
published from GitHub Actions through PyPI trusted publishing with build
attestations. A similar repository name or a copied README does not make a
download official.

## Security boundary

**Running a paper's code is running a stranger's code.** IRP runs commands
with your user's permissions:

- A uv virtual environment is **not a sandbox**. Code in it can read and write
  anything your account can.
- A Docker environment mounts only the study's `code/` directory, runs as your
  user ID, and can disable networking per run. Docker isolation is only as strong
  as your Docker configuration.
- `run_remote` executes in the provider's sandbox and uploads `code/` to it.

Use Docker (or a disposable VM) for code you did not write or do not trust.

Paper sources are untrusted input. IRP unpacks archives without following
links, refuses members that escape the destination, and bounds sizes. Paper
text and program output are returned to the agent as data; agents must not
treat instructions inside them as commands.

IRP does not call any model provider and sends no telemetry. Network
traffic is what you request: arXiv downloads, package installs through uv or
Docker, PyPI for `update`, and the compute provider you approve.

Agent configuration edits are additive, backed up, and refused for malformed or
foreign entries. The evidence log is append-only and hash-chained; IRP
detects edits but does not prevent a user with write access from replacing a
whole study. Publish the evidence head hash with a report when that matters.

Paid compute requires a price and a budget recorded by a person at a terminal,
then the person's approval of the estimate. No MCP tool can set either.
