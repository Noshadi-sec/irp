"""Canonical public identity shared by packaging, setup, MCP, and the skill.

Centralization keeps persistent agent registrations from drifting away from the
PyPI package and the executable declared in pyproject.toml. Renaming the
project means changing this module, pyproject.toml and the skill directory.
"""

from __future__ import annotations

from dataclasses import dataclass

from irp._version import __version__


@dataclass(frozen=True)
class ProductIdentity:
    """Names every adapter must agree on.

    `import_name` is the Python module (`irp`), used for `python -m irp mcp` and
    `import irp`. `package_name` is the PyPI distribution (`irp-agents`, hyphens
    not allowed in a module), used in install specifiers.
    """

    display_name: str
    import_name: str
    package_name: str
    cli_binary: str
    mcp_server_key: str
    skill_name: str
    version: str
    promise: str
    repository: str
    user_agent: str

    @property
    def registration_package_specifier(self) -> str:
        """Exact PyPI pin written into persistent agent registrations."""
        return f"{self.package_name}@{self.version}"

    @property
    def latest_package_specifier(self) -> str:
        return f"{self.package_name}@latest"


PRODUCT = ProductIdentity(
    display_name="IRP",
    import_name="irp",
    package_name="irp-agents",
    cli_binary="irp",
    mcp_server_key="irp",
    skill_name="reproduce-paper",
    version=__version__,
    promise="Build any paper. Prove every claim.",
    repository="https://github.com/Noshadi-sec/irp",
    user_agent=f"irp/{__version__} (+https://github.com/Noshadi-sec/irp)",
)

# Directory names inside a study. They are part of the evidence contract:
# report provenance and `verify` refer to files by these relative paths.
STUDY_MANIFEST = "irp.json"
EVIDENCE_LOG = "evidence.jsonl"
PAPER_DIR = "paper"
CODE_DIR = "code"
RUNS_DIR = "runs"
ENVS_DIR = "envs"
REPORT_MD = "report.md"
REPORT_JSON = "report.json"

STUDY_SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 1
