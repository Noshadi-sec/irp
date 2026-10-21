"""Child process that talks to Modal; see irp.providers.compute.modal.

Usage: python -m irp.providers.compute.modal_worker SPEC.json
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any


def main(spec_path: str) -> int:
    import modal

    spec: dict[str, Any] = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    result: dict[str, Any] = {"status": "error", "exit_code": None, "outputs": {}}
    started = time.time()
    try:
        app = modal.App.lookup(spec["app_name"], create_if_missing=True)
        image = modal.Image.debian_slim(python_version=spec["python"])
        if spec.get("requirements"):
            image = image.pip_install_from_requirements(spec["requirements"])
        try:
            image = image.add_local_dir(
                spec["code_dir"], remote_path="/work", ignore=[".git", "**/__pycache__"]
            )
        except TypeError:
            image = image.add_local_dir(spec["code_dir"], remote_path="/work")
        gpu = spec["gpu"] if spec["gpu_count"] == 1 else f"{spec['gpu']}:{spec['gpu_count']}"
        sandbox = modal.Sandbox.create(
            app=app, image=image, gpu=gpu, timeout=int(spec["timeout_s"]), workdir="/work"
        )
        try:
            process = sandbox.exec("sh", "-c", spec["command"])
            stdout = process.stdout.read()
            stderr = process.stderr.read()
            process.wait()
            result["exit_code"] = process.returncode
            result["stdout"] = stdout
            result["stderr"] = stderr
            for relative in spec.get("outputs", []):
                try:
                    with sandbox.open(f"/work/{relative}", "rb") as handle:
                        result["outputs"][relative] = {
                            "base64": base64.b64encode(handle.read()).decode()
                        }
                except Exception as exc:  # noqa: BLE001 - report each missing output, keep the rest
                    result["outputs"][relative] = {"error": str(exc)}
            result["status"] = "succeeded" if process.returncode == 0 else "failed"
        finally:
            sandbox.terminate()
    except Exception as exc:  # noqa: BLE001 - the parent reads the error from the result file
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["duration_s"] = round(time.time() - started, 3)
    Path(spec["result_path"]).write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
