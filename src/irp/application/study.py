"""A study directory: one paper, its code, its runs, and the evidence log that ties them together.

<study>/
  irp.json     manifest (identity and layout; never a source of results)
  evidence.jsonl    hash-chained, append-only log; the only source of truth
  paper/            fetched paper, outline and page images (never redistributed)
  code/             the implementation, a git repository
  envs/<name>/      environments: lock files, requirements, Dockerfiles
  runs/<id>/        stdout, stderr and archived small outputs of each run
  report.md/.json   written only from the evidence log
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from irp.application.evidence_log import EvidenceLog, utc_now
from irp.domain.errors import ErrorCode, IRPError
from irp.domain.state import StudyState, replay
from irp.filesystem import atomic_write_text, posix_relative
from irp.identity import (
    CODE_DIR,
    ENVS_DIR,
    EVIDENCE_LOG,
    PAPER_DIR,
    PRODUCT,
    RUNS_DIR,
    STUDY_MANIFEST,
    STUDY_SCHEMA_VERSION,
)

CODE_GITIGNORE = """# Written by IRP. Environments and large artifacts stay out of the code history.
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/
.ipynb_checkpoints/
"""

STUDY_GITIGNORE = """# Written by IRP. The paper is never redistributed; environments are rebuildable.
paper/
envs/*/venv/
*.lock
"""


@dataclass
class Study:
    root: Path
    manifest: dict[str, Any]

    @property
    def log(self) -> EvidenceLog:
        return EvidenceLog(self.root / EVIDENCE_LOG)

    @property
    def paper_dir(self) -> Path:
        return self.root / PAPER_DIR

    @property
    def code_dir(self) -> Path:
        return self.root / CODE_DIR

    @property
    def runs_dir(self) -> Path:
        return self.root / RUNS_DIR

    @property
    def envs_dir(self) -> Path:
        return self.root / ENVS_DIR

    @property
    def study_id(self) -> str:
        return str(self.manifest["study_id"])

    def state(self) -> StudyState:
        return replay(self.log.read_verified())

    def rel(self, path: Path) -> str:
        return posix_relative(path, self.root)


def resolve_study_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"The study path must be absolute, got {raw!r}.",
            remediation="Pass the full path, e.g. /home/me/studies/attention.",
        )
    return path.resolve()


def open_study(raw: str) -> Study:
    root = resolve_study_path(raw)
    manifest_path = root / STUDY_MANIFEST
    if not manifest_path.is_file():
        raise IRPError(
            ErrorCode.STUDY_NOT_FOUND,
            f"{root} is not an IRP study.",
            remediation="Call fetch_paper with this study path to create it.",
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IRPError(
            ErrorCode.STUDY_INVALID, f"{manifest_path} is not valid JSON: {exc}"
        ) from exc
    if manifest.get("schema") != STUDY_SCHEMA_VERSION:
        raise IRPError(
            ErrorCode.STUDY_INVALID,
            f"{root} uses study schema {manifest.get('schema')}; this IRP reads schema {STUDY_SCHEMA_VERSION}.",
            remediation="Use the IRP version that created the study, or update IRP.",
        )
    return Study(root=root, manifest=manifest)


def git_executable() -> str | None:
    return shutil.which("git")


def git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    executable = git_executable()
    if executable is None:
        raise IRPError(ErrorCode.PROVIDER_UNAVAILABLE, "git is not on PATH.")
    # IRP's own commits never run the user's hooks, sign, or prompt for identity.
    base = [
        executable,
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "user.name=IRP",
        "-c",
        "user.email=irp-agents@localhost",
    ]
    result = subprocess.run(
        [*base, *args], cwd=cwd, capture_output=True, text=True, timeout=120, check=False
    )
    if check and result.returncode != 0:
        raise IRPError(
            ErrorCode.EXECUTION_FAILURE,
            f"git {' '.join(args)} failed: {result.stderr.strip()[:500]}",
        )
    return result


def create_study(raw: str, *, paper_ref: str, actor: str) -> Study:
    """Create the layout, a git repository for code/, and the first evidence record."""
    root = resolve_study_path(raw)
    if root.exists() and any(root.iterdir()):
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"{root} exists and is not empty, and it is not an IRP study.",
            remediation="Choose a new directory for the study.",
        )
    for directory in (PAPER_DIR, CODE_DIR, RUNS_DIR, ENVS_DIR):
        (root / directory).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": STUDY_SCHEMA_VERSION,
        "study_id": uuid.uuid4().hex[:12],
        "created_at": utc_now(),
        "created_by": f"{PRODUCT.package_name} {PRODUCT.version}",
        "paper_ref": paper_ref,
    }
    atomic_write_text(root / STUDY_MANIFEST, json.dumps(manifest, indent=2) + "\n")
    atomic_write_text(root / ".gitignore", STUDY_GITIGNORE)
    code = root / CODE_DIR
    atomic_write_text(code / ".gitignore", CODE_GITIGNORE)
    git_state: dict[str, Any] = {"initialized": False}
    if git_executable() is not None:
        git(["init", "-q", "-b", "main"], code)
        git(["add", "-A"], code)
        git(["commit", "-q", "--no-verify", "-m", "irp: start study"], code)
        git_state = {"initialized": True, "commit": head_commit(code)}
    study = Study(root=root, manifest=manifest)
    study.log.append(
        "study.created",
        {
            "study_id": manifest["study_id"],
            "paper_ref": paper_ref,
            "layout": {"paper": PAPER_DIR, "code": CODE_DIR, "runs": RUNS_DIR, "envs": ENVS_DIR},
            "code_git": git_state,
        },
        actor=actor,
    )
    return study


def head_commit(code_dir: Path) -> str | None:
    if git_executable() is None or not (code_dir / ".git").exists():
        return None
    result = git(["rev-parse", "HEAD"], code_dir, check=False)
    return result.stdout.strip() or None


def code_state(code_dir: Path, *, commit_message: str | None) -> dict[str, Any]:
    """Name the exact code: commit it first when asked, else report whether it is dirty."""
    if git_executable() is None or not (code_dir / ".git").exists():
        return {"vcs": None, "tree_sha256": tree_digest(code_dir)}
    if commit_message is not None:
        git(["add", "-A"], code_dir)
        staged = git(["diff", "--cached", "--quiet"], code_dir, check=False)
        if staged.returncode != 0:
            git(["commit", "-q", "--no-verify", "-m", commit_message], code_dir)
    status = git(["status", "--porcelain"], code_dir, check=False)
    return {
        "vcs": "git",
        "commit": head_commit(code_dir),
        "dirty": bool(status.stdout.strip()),
    }


def tree_digest(root: Path) -> str:
    """Digest of every regular file's path and content under `root` (VCS and cache directories excluded)."""
    import hashlib

    from irp.providers.compute.local import snapshot_tree

    digest = hashlib.sha256()
    for relative in sorted(snapshot_tree(root)):
        digest.update(relative.encode("utf-8") + b"\0")
        with (root / relative).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def code_has_content(code_dir: Path) -> bool:
    """True once code/ holds anything besides IRP's scaffolding."""
    from irp.providers.compute.local import snapshot_tree

    return any(path not in {".gitignore"} for path in snapshot_tree(code_dir))
