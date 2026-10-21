"""setup, doctor and uninstall against a temporary home with real-looking agent configs."""

import json
import os
from pathlib import Path

import tomlkit

from irp.application.doctor import run_doctor
from irp.application.registration import registration_command
from irp.application.setup import SetupOptions, run_setup
from irp.application.uninstall import run_uninstall


def home() -> Path:
    return Path(os.environ["HOME"])


def seed_configs() -> None:
    (home() / ".claude").mkdir()
    (home() / ".claude.json").write_text(
        json.dumps({"numStartups": 7, "mcpServers": {"other": {"command": "other-mcp"}}}, indent=2)
    )
    (home() / ".codex").mkdir()
    (home() / ".codex" / "config.toml").write_text(
        '# my codex settings\nmodel = "gpt-x"\n\n[mcp_servers.other]\ncommand = "other"\n'
    )
    (home() / ".cursor").mkdir()
    (home() / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {}}))


def test_dry_run_plans_without_writing():
    seed_configs()
    before = (home() / ".claude.json").read_text()
    result = run_setup(SetupOptions(clients=["claude_code"], dry_run=True))
    assert result["status"] == "planned"
    kinds = [a["kind"] for a in result["planned_actions"]]
    assert kinds == ["configure_client", "install_skill"]
    assert (home() / ".claude.json").read_text() == before
    assert not (home() / ".claude" / "skills").exists()


def test_without_scope_or_approval_nothing_is_written():
    seed_configs()
    result = run_setup(SetupOptions(clients=["cursor"]))
    assert result["status"] == "needs_confirmation"
    assert "irp" not in json.loads((home() / ".cursor" / "mcp.json").read_text())["mcpServers"]
    # --yes with no scope only refreshes existing IRP registrations: here there are none.
    assert run_setup(SetupOptions(approved=True))["planned_actions"] == []


def test_setup_is_additive_backed_up_and_idempotent():
    seed_configs()
    result = run_setup(SetupOptions(clients=["claude_code", "codex", "cursor"], approved=True))
    assert result["status"] == "ready", result
    command = registration_command()
    claude = json.loads((home() / ".claude.json").read_text())
    assert claude["numStartups"] == 7 and "other" in claude["mcpServers"]
    assert claude["mcpServers"]["irp"] == {"command": command[0], "args": command[1:]}
    assert (home() / ".claude.json.irp.backup").is_file()
    codex_text = (home() / ".codex" / "config.toml").read_text()
    assert codex_text.startswith("# my codex settings"), "comments survive"
    codex = tomlkit.parse(codex_text)
    assert codex["mcp_servers"]["irp"]["tool_timeout_sec"] == 1800
    assert codex["mcp_servers"]["other"]["command"] == "other"
    assert (home() / ".claude" / "skills" / "reproduce-paper" / "SKILL.md").is_file()
    assert (home() / ".agents" / "skills" / "reproduce-paper" / ".irp-skill.json").is_file()
    assert set(result["restart"]) == {"Claude Code", "Codex", "Cursor"}

    again = run_setup(SetupOptions(clients=["claude_code", "codex", "cursor"], approved=True))
    assert again["planned_actions"] == [] and again["status"] == "ready"


def test_user_settings_on_the_entry_are_kept():
    seed_configs()
    run_setup(SetupOptions(clients=["codex"], approved=True))
    path = home() / ".codex" / "config.toml"
    document = tomlkit.parse(path.read_text())
    document["mcp_servers"]["irp"]["tool_timeout_sec"] = 7200
    document["mcp_servers"]["irp"]["args"] = ["irp-agents@0.0.1", "mcp"]
    document["mcp_servers"]["irp"]["command"] = "uvx"
    path.write_text(tomlkit.dumps(document))
    result = run_setup(SetupOptions(approved=True))
    assert result["selected_clients"] == ["codex"], (
        "existing registrations are refreshed with --yes alone"
    )
    updated = tomlkit.parse(path.read_text())["mcp_servers"]["irp"]
    assert updated["tool_timeout_sec"] == 7200
    assert list(updated["args"]) == registration_command()[1:]


def test_foreign_entries_and_malformed_files_block_setup():
    seed_configs()
    (home() / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"irp": {"command": "something-else"}}})
    )
    blocked = run_setup(SetupOptions(clients=["cursor"], approved=True))
    assert blocked["status"] == "needs_human" and "did not write" in blocked["remediation"]
    (home() / ".cursor" / "mcp.json").write_text("{ // comments are not JSON\n}")
    malformed = run_setup(SetupOptions(clients=["cursor"], approved=True))
    assert malformed["status"] == "needs_human"
    assert (home() / ".cursor" / "mcp.json").read_text().startswith("{ //"), "never rewritten"


def test_unmanaged_skill_directory_is_left_alone():
    seed_configs()
    own = home() / ".claude" / "skills" / "reproduce-paper"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("my own skill")
    result = run_setup(SetupOptions(clients=["claude_code"], approved=True))
    assert result["status"] == "needs_human"
    assert (own / "SKILL.md").read_text() == "my own skill"
    skipped = run_setup(SetupOptions(clients=["claude_code"], install_skill=False, approved=True))
    assert skipped["status"] == "ready"


def test_doctor_scopes_and_detects_drift():
    seed_configs()
    scoped = run_doctor(clients=["claude_code"], skill=False)
    assert scoped["scope"]["mode"] == "explicit" and scoped["healthy"] is False
    run_setup(SetupOptions(clients=["claude_code"], approved=True))
    assert run_doctor(clients=["claude_code"], skill=True)["healthy"] is True
    registrations = {
        r["client"]: r["state"]
        for r in run_doctor(clients=[], skill=False)["identity"]["registrations"]
    }
    assert registrations == {"claude_code": "aligned", "codex": "missing", "cursor": "missing"}


def test_uninstall_removes_only_what_irp_owns():
    seed_configs()
    run_setup(SetupOptions(clients=["claude_code", "cursor"], approved=True))
    plan = run_uninstall(approved=False, dry_run=True)
    assert len(plan["planned_actions"]) == 4
    result = run_uninstall(approved=True, dry_run=False)
    assert result["status"] == "removed"
    claude = json.loads((home() / ".claude.json").read_text())
    assert "irp" not in claude["mcpServers"] and "other" in claude["mcpServers"]
    assert not (home() / ".claude" / "skills" / "reproduce-paper").exists()
    assert run_uninstall(approved=True, dry_run=False)["status"] == "nothing_to_remove"


def test_claude_config_dir_profile_is_respected(monkeypatch, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(profile))
    run_setup(SetupOptions(clients=["claude_code"], approved=True))
    assert "irp" in json.loads((profile / ".claude.json").read_text())["mcpServers"]
    assert (profile / "skills" / "reproduce-paper" / "SKILL.md").is_file()
    assert not (home() / ".claude.json").exists()


def test_skill_only_setup_installs_the_shared_copy_and_is_ready():
    result = run_setup(SetupOptions(install_skill=True, approved=True))
    assert result["status"] == "ready", result
    assert (home() / ".agents" / "skills" / "reproduce-paper" / "SKILL.md").is_file()


def test_doctor_skill_scope_requires_an_installed_aligned_copy():
    assert run_doctor(clients=[], skill=True)["healthy"] is False
    run_setup(SetupOptions(install_skill=True, approved=True))
    assert run_doctor(clients=[], skill=True)["healthy"] is True
    skill_md = home() / ".agents" / "skills" / "reproduce-paper" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\nedited\n")
    report = run_doctor(clients=[], skill=True)
    assert report["healthy"] is False
    assert any(s["state"] == "stale" for s in report["identity"]["skills"])
