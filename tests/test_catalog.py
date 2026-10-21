"""Contracts, handlers, CLI commands and the generated docs catalog agree."""

import subprocess
import sys

from irp.application.operations import HANDLERS
from irp.cli.app import app
from irp.contracts.catalog import CATALOG
from tests.conftest import REPO

CLI_FOR_TOOL = {
    "fetch_paper": "fetch",
    "get_section": "section",
    "get_page_image": "page",
    "add_claim": "claim",
    "list_claims": "claim",
    "add_guess": "guess",
    "map_method": "map",
    "add_note": "note",
    "create_env": "env",
    "run": "run",
    "run_status": "run-status",
    "run_remote": "run-remote",
    "extract_metrics": "metrics",
    "compare": "compare",
    "report": "report",
    "verify": "verify",
    "study_status": "status",
}


def test_every_contract_has_one_handler_and_a_cli_command():
    names = [c.name for c in CATALOG]
    assert len(names) == len(set(names))
    assert set(names) == set(HANDLERS) == set(CLI_FOR_TOOL)
    commands = {c.name for c in app.registered_commands} | {g.name for g in app.registered_groups}
    assert set(CLI_FOR_TOOL.values()) <= commands


def test_every_input_field_is_documented():
    for contract in CATALOG:
        for name, field in contract.input_model.model_fields.items():
            assert field.description, f"{contract.name}.{name} has no description"


def test_generated_catalog_in_docs_is_current():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate_catalog.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
