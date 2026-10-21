"""create_env: a pinned uv environment or Docker image with its lock file."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from irp.application.context import OperationContext
from irp.application.study import Study, open_study
from irp.contracts.inputs import CreateEnvInput
from irp.domain.errors import ErrorCode, IRPError, rule_violation
from irp.domain.state import StudyState
from irp.filesystem import atomic_write_text, contained_path, sha256_file
from irp.providers.environments import docker as docker_env
from irp.providers.environments import uv as uv_env


def require_claims_first(state: StudyState, action: str) -> None:
    """Rule 5: every claim is recorded before code is built or run."""
    if not state.claims:
        raise rule_violation(
            5,
            f"No claims are recorded, so {action} is refused.",
            remediation="Read the paper and record every claim with add_claim first.",
        )


def _requirements(study: Study, request: CreateEnvInput) -> Path | None:
    if request.requirements is not None:
        path = contained_path(study.code_dir, request.requirements, what="requirements")
        if not path.is_file():
            raise IRPError(ErrorCode.NOT_FOUND, f"code/{request.requirements} does not exist.")
        return path
    default = study.code_dir / "requirements.txt"
    return default if default.is_file() else None


def create_env(request: CreateEnvInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    require_claims_first(state, "building an environment")
    if request.name in state.envs:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"Environment {request.name!r} already exists.",
            remediation="Environments are never rebuilt in place so earlier runs keep their lock; "
            "create one with a new name.",
        )
    env_dir = study.envs_dir / request.name
    requirements = _requirements(study, request)
    record: dict[str, Any] = {
        "name": request.name,
        "backend": request.backend,
        "requested_python": request.python,
        "requirements": study.rel(requirements) if requirements else None,
        "requirements_sha256": sha256_file(requirements) if requirements else None,
        "packages": request.packages,
        "gpu": request.gpu,
    }
    if request.backend == "uv":
        if request.base_image or request.system_packages:
            raise IRPError(
                ErrorCode.INVALID_REQUEST,
                "base_image and system_packages apply only to backend='docker'.",
            )
        try:
            built = uv_env.create_uv_environment(
                venv=env_dir / "venv",
                python=request.python,
                code_dir=study.code_dir,
                requirements=requirements,
                packages=request.packages,
            )
        except BaseException:
            shutil.rmtree(env_dir, ignore_errors=True)
            raise
        record.update(
            {
                "python": built.python_version,
                "venv": study.rel(built.venv),
                "tool": {"uv": built.uv_version},
                "isolation": "none",
            }
        )
        lock_text = built.lock_text
    else:
        base_image = request.base_image or f"python:{request.python}-slim"
        tag = f"irp/{study.study_id}-{request.name}:latest"
        try:
            built_image = docker_env.build_docker_environment(
                context_dir=env_dir,
                tag=tag,
                base_image=base_image,
                requirements=requirements,
                packages=request.packages,
                system_packages=request.system_packages,
            )
        except BaseException:
            shutil.rmtree(env_dir, ignore_errors=True)
            raise
        docker_env.verify_mount(built_image.tag, study.code_dir)
        record.update(
            {
                "mount_verified": True,
                "python": built_image.python_version,
                "image": built_image.tag,
                "image_id": built_image.image_id,
                "base_image": built_image.base_image,
                "base_digest": built_image.base_digest,
                "dockerfile": study.rel(env_dir / "Dockerfile"),
                "dockerfile_sha256": sha256_file(env_dir / "Dockerfile"),
                "tool": {"docker": built_image.docker_version},
                "isolation": "container",
                "system_packages": request.system_packages,
            }
        )
        lock_text = built_image.lock_text
    env_dir.mkdir(parents=True, exist_ok=True)
    lock_path = env_dir / "lock.txt"
    atomic_write_text(lock_path, lock_text)
    if requirements is not None:
        snapshot = env_dir / "requirements.txt"
        if not snapshot.exists():
            shutil.copyfile(requirements, snapshot)
        record["requirements_snapshot"] = study.rel(snapshot)
    record["lock_file"] = study.rel(lock_path)
    record["lock_sha256"] = sha256_file(lock_path)
    record["locked_packages"] = sum(
        1 for line in lock_text.splitlines() if line.strip() and not line.startswith("#")
    )
    study.log.append("env.created", {"env": record}, actor=context.actor)
    warnings = []
    if request.backend == "uv":
        warnings.append(
            "A virtual environment is not a sandbox: the paper's code runs with your permissions. "
            "Use backend='docker' for code you do not trust."
        )
    return {"env": record, "warnings": warnings}
