"""Repository invariants: pinned actions, working links, consistent translations."""

import re
from pathlib import Path

import pytest

from irp.contracts.catalog import CATALOG
from tests.conftest import REPO

MARKDOWN = sorted(
    [
        *REPO.glob("*.md"),
        *(REPO / "docs").rglob("*.md"),
        *(REPO / ".agents").rglob("*.md"),
        *(REPO / "benchmarks").rglob("*.md"),
        *(REPO / "examples").rglob("*.md"),
    ]
)
LINK = re.compile(r"\]\(([^)\s]+)\)|<img src=\"([^\"]+)\"")


def test_every_workflow_action_is_pinned_to_a_commit():
    for workflow in (REPO / ".github" / "workflows").glob("*.yml"):
        for line in workflow.read_text().splitlines():
            match = re.match(r"\s*(?:-\s+)?uses:\s*(\S+)", line)
            if not match or match.group(1).startswith("./"):
                continue
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", match.group(1)), (
                f"{workflow.name}: {line.strip()}"
            )
            assert re.search(r"# v\d", line), (
                f"{workflow.name}: pinned action needs a version comment: {line.strip()}"
            )


@pytest.mark.parametrize("document", MARKDOWN, ids=lambda p: str(p.relative_to(REPO)))
def test_relative_links_resolve(document: Path):
    text = document.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    for match in LINK.finditer(text):
        target = match.group(1) or match.group(2)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        assert (document.parent / path).exists(), (
            f"{document.relative_to(REPO)} links to missing {target}"
        )


@pytest.mark.parametrize("language", ["zh", "ja", "ko", "es", "it"])
def test_translations_keep_commands_and_links(language):
    text = (REPO / "docs" / "readme" / f"README_{language}.md").read_text(encoding="utf-8")
    for command in (
        "uvx irp-agents setup",
        "irp doctor",
        "irp update",
        "uv tool install irp-agents",
    ):
        assert command in text, f"README_{language} lost `{command}`"
    assert "Noshadi-sec/irp" in text, "the official-sources notice must stay"
    for other in ("zh", "ja", "ko", "es", "it"):
        if other != language:
            assert f"README_{other}.md" in text


def test_readme_lists_every_tool():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for contract in CATALOG:
        assert f"`{contract.name}`" in readme, contract.name


def test_skill_hard_rules_match_the_error_catalog():
    from irp.domain.errors import HARD_RULES

    skill = (REPO / ".agents" / "skills" / "reproduce-paper" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for number in HARD_RULES:
        assert f"{number}. **" in skill, f"rule {number} missing from the skill"
