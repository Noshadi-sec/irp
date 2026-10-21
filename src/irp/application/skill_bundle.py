"""The bundled skill: where it lives in the package, and how setup installs and checks it.

Installed copies carry `.irp-skill.json`, an ownership manifest listing
every file and its hash. Setup only replaces copies it owns; a directory with
the same name and no manifest is someone else's and is left alone.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from irp.filesystem import atomic_write_bytes, sha256_file
from irp.identity import PRODUCT

MANIFEST = ".irp-skill.json"


def bundled_skill_dir() -> Path:
    """Wheel installs carry the skill as package data; a source checkout reads .agents/skills."""
    packaged = Path(str(resources.files("irp"))) / "_bundled_skill" / PRODUCT.skill_name
    if (packaged / "SKILL.md").is_file():
        return packaged
    checkout = Path(__file__).resolve().parents[3] / ".agents" / "skills" / PRODUCT.skill_name
    if (checkout / "SKILL.md").is_file():
        return checkout
    raise FileNotFoundError(
        f"The bundled {PRODUCT.skill_name} skill is missing from this installation. Reinstall {PRODUCT.package_name}."
    )


def skill_version(skill_md: Path) -> str | None:
    """`metadata.version` from the SKILL.md front matter."""
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    version = re.search(r'^\s+version:\s*"?([^"\n]+)"?\s*$', match.group(1), re.MULTILINE)
    return version.group(1).strip() if version else None


def bundle_files(source: Path) -> dict[str, str]:
    return {
        path.relative_to(source).as_posix(): sha256_file(path)
        for path in sorted(source.rglob("*"))
        if path.is_file() and path.name != MANIFEST and "__pycache__" not in path.parts
    }


@dataclass(frozen=True)
class SkillInspection:
    destination: Path
    state: str  # aligned | stale | missing | unmanaged | unknown
    installed_version: str | None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.destination),
            "state": self.state,
            "installed_version": self.installed_version,
            "detail": self.detail,
        }


def inspect_skill(root: Path) -> SkillInspection:
    destination = root / PRODUCT.skill_name
    if destination.is_symlink() or root.is_symlink():
        return SkillInspection(
            destination, "unmanaged", None, "a symbolic link; setup will not follow it"
        )
    if not destination.exists():
        return SkillInspection(destination, "missing", None)
    if not destination.is_dir():
        return SkillInspection(destination, "unmanaged", None, "not a directory")
    manifest_path = destination / MANIFEST
    if not manifest_path.is_file():
        return SkillInspection(destination, "unmanaged", None, "no IRP ownership manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SkillInspection(destination, "unknown", None, "unreadable ownership manifest")
    expected = bundle_files(bundled_skill_dir())
    installed = {
        relative: sha256_file(destination / relative)
        for relative in manifest.get("files", {})
        if (destination / relative).is_file()
    }
    state = "aligned" if installed == expected and manifest.get("files") == expected else "stale"
    return SkillInspection(destination, state, manifest.get("skill_version"))


def install_skill(root: Path) -> dict[str, Any]:
    """Install or refresh an owned copy; refuse unmanaged destinations."""
    inspection = inspect_skill(root)
    if inspection.state in ("unmanaged", "unknown"):
        return {
            "status": "failed",
            "path": str(inspection.destination),
            "detail": inspection.detail,
        }
    source = bundled_skill_dir()
    files = bundle_files(source)
    destination = inspection.destination
    destination.mkdir(parents=True, exist_ok=True)
    previous: dict[str, str] = {}
    if (destination / MANIFEST).is_file():
        previous = json.loads((destination / MANIFEST).read_text(encoding="utf-8")).get("files", {})
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, (source / relative).read_bytes())
    for relative in set(previous) - set(files):
        stale = destination / relative
        if stale.is_file() and not stale.is_symlink():
            stale.unlink()
    manifest = {
        "package": PRODUCT.package_name,
        "package_version": PRODUCT.version,
        "skill": PRODUCT.skill_name,
        "skill_version": skill_version(source / "SKILL.md"),
        "files": files,
    }
    atomic_write_bytes(
        destination / MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    )
    after = inspect_skill(root)
    if after.state != "aligned":
        return {
            "status": "failed",
            "path": str(destination),
            "detail": "the installed copy did not verify",
        }
    return {
        "status": "installed",
        "path": str(destination),
        "skill_version": manifest["skill_version"],
    }


def remove_skill(root: Path) -> dict[str, Any]:
    destination = root / PRODUCT.skill_name
    inspection = inspect_skill(root)
    if inspection.state == "missing":
        return {"status": "absent", "path": str(destination)}
    if inspection.state in ("unmanaged", "unknown"):
        return {"status": "kept", "path": str(destination), "detail": inspection.detail}
    manifest = json.loads((destination / MANIFEST).read_text(encoding="utf-8"))
    for relative in manifest.get("files", {}):
        path = destination / relative
        if path.is_file() and not path.is_symlink():
            path.unlink()
    (destination / MANIFEST).unlink()
    for directory in sorted(
        (p for p in destination.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    if not any(destination.iterdir()):
        destination.rmdir()
        return {"status": "removed", "path": str(destination)}
    return {
        "status": "partially_removed",
        "path": str(destination),
        "detail": "files not written by IRP were kept",
    }
