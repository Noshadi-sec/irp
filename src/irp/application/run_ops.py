"""run, run_status and run_remote."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any

from irp.application.context import OperationContext
from irp.application.env_ops import require_claims_first
from irp.application.evidence_log import utc_now
from irp.application.runner import (
    execute_recorded_run,
    mark_lost_runs,
    run_dir,
    write_runner_marker,
)
from irp.application.study import Study, code_state, open_study
from irp.contracts.inputs import RunInput, RunRemoteInput, RunStatusInput
from irp.domain.errors import ErrorCode, IRPError, not_found, rule_violation
from irp.domain.state import StudyState
from irp.filesystem import contained_path
from irp.providers.compute import local, pricing
from irp.providers.compute.modal import SUPPORTED_GPUS, modal_status
from irp.providers.environments import docker as docker_env
from irp.providers.environments import uv as uv_env

TAIL_BYTES = 64 * 1024


def _refuse_concurrent(study: Study, context: OperationContext) -> StudyState:
    """One run at a time per study: changed-file attribution needs exclusive use of code/."""
    mark_lost_runs(study, actor=context.actor)
    state = study.state()
    running = [run_id for run_id, run in state.runs.items() if run.completed is None]
    if running:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"Run {running[0]} is still running.",
            remediation=f"Wait for it with run_status run_id='{running[0]}' wait_s=600 before starting another.",
            details={"running": running},
        )
    return state


def _seed_vars(run_id: str, study: Study, seed: int | None) -> dict[str, str]:
    variables = {
        "IRP_RUN_ID": run_id,
        "IRP_STUDY": str(study.root),
        "PYTHONUNBUFFERED": "1",
    }
    if seed is not None:
        variables["IRP_SEED"] = str(seed)
        variables["PYTHONHASHSEED"] = str(seed)
    return variables


def run(request: RunInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    require_claims_first(state, "running code")
    state = _refuse_concurrent(study, context)
    env = None
    if request.env is not None:
        env = state.envs.get(request.env)
        if env is None:
            raise IRPError(
                ErrorCode.NOT_FOUND,
                f"No environment {request.env!r}.",
                remediation="Create it with create_env, or pass env=null to use the host environment.",
            )
    is_docker = env is not None and env["backend"] == "docker"
    if not is_docker and (not request.network or request.memory_limit):
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            "network=false and memory_limit need a Docker environment.",
            remediation="Create an environment with backend='docker' to isolate runs.",
        )
    cwd_path = (
        contained_path(study.code_dir, request.cwd, what="cwd")
        if request.cwd != "."
        else study.code_dir
    )
    if not cwd_path.is_dir():
        raise IRPError(ErrorCode.NOT_FOUND, f"code/{request.cwd} is not a directory.")
    run_id = state.next_id("run")
    variables = _seed_vars(run_id, study, request.seed)
    spec: dict[str, Any] = {
        "id": run_id,
        "command": request.command,
        "env": request.env,
        "scope": request.scope,
        "seed": request.seed,
        "cwd": cwd_path.relative_to(study.code_dir.resolve()).as_posix() or ".",
        "timeout_s": request.timeout_s,
        "compute": "local",
        "note": request.note,
        "requested_at": utc_now(),
        "detached": not request.wait,
    }
    if is_docker:
        assert env is not None
        docker_env.verify_mount(env["image"], study.code_dir)
        variables["HOME"] = "/tmp"  # noqa: S108 - HOME inside the container, not on the host
        workdir = spec["cwd"] if spec["cwd"] != "." else ""
        spec["launcher"] = docker_env.docker_run_command(
            image=env["image"],
            code_dir=study.code_dir,
            workdir=workdir,
            command=request.command,
            env={k: v for k, v in variables.items() if k != "IRP_STUDY"},
            network=request.network,
            gpu=bool(env.get("gpu")),
            memory_limit=request.memory_limit,
        )
        spec["isolation"] = "container"
        spec["network"] = request.network
        spec["env_vars"] = {}
    else:
        spec["launcher"] = local.shell_argv(request.command)
        spec["isolation"] = "none"
        spec["env_vars"] = variables
        if env is not None:
            venv = study.root / env["venv"]
            spec["path_prefix"] = [study.rel(uv_env.venv_bin(venv))]
            spec["VIRTUAL_ENV_REL"] = env["venv"]
    spec["code_state"] = code_state(
        study.code_dir,
        commit_message=f"irp: code for run {run_id}" if request.commit else None,
    )
    study.log.append("run.started", {"run": spec}, actor=context.actor)
    return _start(study, run_id, wait=request.wait, context=context)


def _start(study: Study, run_id: str, *, wait: bool, context: OperationContext) -> dict[str, Any]:
    if wait:
        completed = execute_recorded_run(study, run_id, actor=context.actor)
        return _summary(study, run_id, completed, tail_lines=20)
    directory = run_dir(study, run_id)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "runner.log").open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "irp.application.runner", str(study.root), run_id],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=sys.platform != "win32",
            close_fds=True,
        )
    write_runner_marker(study, run_id, process.pid)
    return {
        "run_id": run_id,
        "status": "running",
        "next": f"Poll with run_status run_id='{run_id}' wait_s=600 until it finishes.",
    }


def _tail(path: Any, lines: int) -> str:
    if lines == 0 or not path.is_file():
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - TAIL_BYTES))
        data = handle.read().decode("utf-8", errors="replace")
    return "\n".join(data.splitlines()[-lines:])


def _summary(
    study: Study, run_id: str, completed: dict[str, Any] | None, *, tail_lines: int
) -> dict[str, Any]:
    state = study.state()
    run = state.runs[run_id]
    directory = run_dir(study, run_id)
    summary: dict[str, Any] = {
        "run_id": run_id,
        "status": run.status,
        "scope": run.started.get("scope"),
        "seed": run.started.get("seed"),
        "counts": run.counts_as_reproduction,
        "code_state": run.started.get("code_state"),
    }
    if completed is not None:
        summary.update(
            {
                "exit_code": completed.get("exit_code"),
                "duration_s": completed.get("duration_s"),
                "max_rss_bytes": completed.get("max_rss_bytes"),
                "outputs": [o["path"] for o in completed.get("outputs", [])][:30],
                "outputs_total": len(completed.get("outputs", [])),
                "error": completed.get("error"),
            }
        )
    summary["stdout_tail"] = _tail(directory / "stdout.txt", tail_lines)
    summary["stderr_tail"] = _tail(directory / "stderr.txt", tail_lines)
    if completed is not None and completed.get("status") != "succeeded":
        summary["next"] = (
            "Read the error. Fix a bug in your implementation and run again, or, if the paper's method "
            "cannot run here, record could_not_run with compare and the blocking error (rule 3). Never "
            "change the paper's method to make the run succeed (rule 2)."
        )
    elif completed is not None:
        summary["next"] = (
            "Extract the numbers with extract_metrics from stdout or the files this run wrote."
        )
    return summary


def run_status(request: RunStatusInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    if request.run_id not in study.state().runs:
        raise not_found("run", request.run_id)
    deadline = time.monotonic() + request.wait_s
    while True:
        mark_lost_runs(study, actor=context.actor)
        run = study.state().runs[request.run_id]
        if run.completed is not None or time.monotonic() >= deadline:
            break
        time.sleep(1.0)
    return _summary(study, request.run_id, run.completed, tail_lines=request.tail_lines)


def run_remote(request: RunRemoteInput, context: OperationContext) -> dict[str, Any]:
    study = open_study(request.study)
    state = study.state()
    require_claims_first(state, "paid compute")
    if request.provider != "modal":
        raise IRPError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            f"The {request.provider} provider is planned but not available yet.",
            remediation="Use provider='modal', or run locally.",
        )
    if request.gpu not in SUPPORTED_GPUS:
        raise IRPError(
            ErrorCode.INVALID_REQUEST,
            f"Unknown Modal GPU {request.gpu!r}.",
            details={"supported": list(SUPPORTED_GPUS)},
        )
    env = state.envs.get(request.env)
    if env is None:
        raise IRPError(
            ErrorCode.NOT_FOUND,
            f"No environment {request.env!r}.",
            remediation="Create one with create_env; the remote sandbox installs its requirements.",
        )
    price = state.prices.get(f"modal:{request.gpu}")
    if price is None:
        raise rule_violation(
            6,
            f"No price is recorded for Modal {request.gpu}, so no estimate can be shown.",
            remediation="Ask the person to check https://modal.com/pricing and run: irp budget price "
            f"--study {study.root} --provider modal --gpu {request.gpu} --usd-per-hour <price>",
        )
    estimate = pricing.estimate(
        provider="modal",
        gpu=request.gpu,
        gpu_count=request.gpu_count,
        hours=request.hours,
        price=price,
    )
    remaining = round(state.budget_usd - state.spent_usd(), 4)
    if estimate["usd"] > remaining:
        raise rule_violation(
            6,
            f"The estimate (${estimate['usd']:.2f}) exceeds the remaining budget (${remaining:.2f}).",
            remediation="Ask the person whether to raise the budget (irp budget set --study "
            f"{study.root} --usd <amount>), or reduce hours or GPUs.",
            details={
                "estimate": estimate,
                "budget_usd": state.budget_usd,
                "spent_usd": state.spent_usd(),
            },
        )
    if not request.approved:
        raise IRPError(
            ErrorCode.NEEDS_CONFIRMATION,
            f"Paid compute needs the person's approval (rule 6): about ${estimate['usd']:.2f} for "
            f"{request.gpu_count}x {request.gpu} up to {request.hours:g} h.",
            remediation="Show the person this estimate. Only if they approve, call run_remote again with approved=true.",
            details={"estimate": estimate, "remaining_budget_usd": remaining},
        )
    usable, detail = modal_status()
    if not usable:
        raise IRPError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            f"Modal is not available: {detail}.",
            remediation="Install irp-agents[modal] and authenticate with `modal setup`.",
        )
    state = _refuse_concurrent(study, context)
    for output in request.outputs:
        contained_path(study.code_dir, output, what="output")
    run_id = state.next_id("run")
    python_minor = ".".join(str(env.get("python") or env["requested_python"]).split(".")[:2])
    spec: dict[str, Any] = {
        "id": run_id,
        "command": request.command,
        "env": request.env,
        "scope": request.scope,
        "seed": request.seed,
        "cwd": ".",
        "timeout_s": int(request.hours * 3600),
        "compute": "modal",
        "isolation": "cloud-sandbox",
        "provider": "modal",
        "gpu": request.gpu,
        "gpu_count": request.gpu_count,
        "hours": request.hours,
        "estimate": estimate,
        "approved": True,
        "python": python_minor,
        "requirements": env.get("requirements_snapshot"),
        "outputs": request.outputs,
        "note": request.note,
        "requested_at": utc_now(),
        "detached": not request.wait,
        "launcher": ["modal-sandbox", "sh", "-c", request.command],
        "env_vars": {},
        "code_state": code_state(study.code_dir, commit_message=f"irp: code for run {run_id}"),
    }
    study.log.append("run.started", {"run": spec}, actor=context.actor)
    result = _start(study, run_id, wait=request.wait, context=context)
    result["estimate"] = estimate
    result["warning"] = (
        "The Modal adapter is experimental; no real-provider verification is recorded yet."
    )
    return result
