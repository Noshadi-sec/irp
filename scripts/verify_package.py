"""Build (or take) a wheel, install it into an empty environment, and exercise what users get.

Usage: python scripts/verify_package.py [path/to/irp-*.whl]

Checks the installed CLI, the real stdio MCP server, the bundled skill, setup's
plan in an isolated home, and a small study end to end. Release CI runs this on
the exact wheel it publishes. Needs uv on PATH.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from irp.identity import PRODUCT  # noqa: E402

TOY = REPO / "examples" / "toy-paper" / "paper"
CODE = """import os, random
rng = random.Random(int(os.environ["IRP_SEED"]))
xs = [rng.random() for _ in range(10000)]
ys = [2 * x + 1 + rng.gauss(0, 0.1) for x in xs]
mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
print(f"slope: {sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs):.6f}")
"""


def step(name: str) -> None:
    print(f"- {name}", flush=True)


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)  # type: ignore[call-overload]
    if result.returncode != 0:
        raise SystemExit(f"FAILED: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def build(out: Path) -> Path:
    run(["uv", "build", "--out-dir", str(out)], cwd=REPO)
    wheels = sorted(out.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected one wheel, found {wheels}")
    return wheels[0]


def check_wheel(wheel: Path) -> None:
    names = set(zipfile.ZipFile(wheel).namelist())
    required = {
        "irp/py.typed",
        f"irp/_bundled_skill/{PRODUCT.skill_name}/SKILL.md",
        f"irp/_bundled_skill/{PRODUCT.skill_name}/references/claims-and-verdicts.md",
    }
    missing = required - names
    if missing:
        raise SystemExit(f"wheel is missing {sorted(missing)}")
    if any(name.startswith(("tests/", "examples/")) for name in names):
        raise SystemExit("wheel contains tests or examples")


async def check_mcp(executable: Path, env: dict[str, str]) -> None:
    from mcp import Client, StdioServerParameters

    params = StdioServerParameters(command=str(executable), args=["mcp"], env=env)
    async with Client(params) as client:
        tools = [tool.name for tool in (await client.list_tools()).tools]
        if len(tools) != 17 or tools[0] != "fetch_paper":
            raise SystemExit(f"unexpected MCP catalog: {tools}")
        result = await client.call_tool("study_status", {"study": "/nonexistent/irp-check"})
        error = json.loads(result.content[0].text)["error"]
        if not result.is_error or error["code"] != "study_not_found":
            raise SystemExit(f"unexpected MCP error projection: {result}")


def main(argv: list[str]) -> int:
    if shutil.which("uv") is None:
        raise SystemExit("uv is required")
    with tempfile.TemporaryDirectory(prefix="irp-verify-") as raw:
        work = Path(raw)
        wheel = Path(argv[0]).resolve() if argv else build(work / "dist")
        step(f"wheel {wheel.name}")
        check_wheel(wheel)
        venv = work / "venv"
        run(
            [
                "uv",
                "venv",
                str(venv),
                "--python",
                f"{sys.version_info.major}.{sys.version_info.minor}",
            ]
        )
        python = venv / "bin" / "python"
        run(["uv", "pip", "install", "--python", str(python), str(wheel)])
        irp = venv / "bin" / "irp"
        home = work / "home"
        home.mkdir()
        env = {"HOME": str(home), "PATH": f"{venv / 'bin'}:{os.environ.get('PATH', '')}"}

        step("version")
        version = run([str(irp), "--version"], env=env).stdout.strip()
        if version != PRODUCT.version:
            raise SystemExit(f"installed {version}, expected {PRODUCT.version}")

        step("catalog")
        tools = json.loads(run([str(irp), "tools", "--json"], env=env).stdout)["tools"]
        if len(tools) != 17:
            raise SystemExit(f"expected 17 tools, found {len(tools)}")

        step("stdio MCP server")
        asyncio.run(check_mcp(irp, env))

        step("setup plan uses the bundled skill")
        (home / ".claude").mkdir()
        plan = json.loads(
            run(
                [str(irp), "setup", "--client", "claude_code", "--dry-run", "--json"], env=env
            ).stdout
        )
        kinds = [action["kind"] for action in plan["planned_actions"]]
        if kinds != ["configure_client", "install_skill"]:
            raise SystemExit(f"unexpected setup plan: {plan}")
        command = plan["registration_command"]
        registered_in_venv = Path(command[0]).parent.resolve() == (venv / "bin").resolve()
        if not registered_in_venv or command[1:] != ["-m", PRODUCT.import_name, "mcp"]:
            raise SystemExit(f"unexpected registration command: {command}")

        step("study end to end")
        study = str(work / "study")
        run([str(irp), "fetch", str(TOY), "--study", study, "--json"], env=env)
        run(
            [
                str(irp),
                "claim",
                "add",
                "--study",
                study,
                "--statement",
                "Slope",
                "--metric",
                "slope",
                "--value",
                "2.00",
                "--where",
                "Table 1",
                "--tol-abs",
                "0.02",
                "--json",
            ],
            env=env,
        )
        (Path(study) / "code" / "fit.py").write_text(CODE, encoding="utf-8")
        run(
            [
                str(irp),
                "run",
                "--study",
                study,
                "--no-env",
                "--seed",
                "0",
                "--json",
                "--",
                str(python),
                "fit.py",
            ],
            env=env,
        )
        run([str(irp), "metrics", "r1", "--study", study, "--key", "slope", "--json"], env=env)
        verdict = json.loads(
            run([str(irp), "compare", "c1", "--study", study, "-m", "m1", "--json"], env=env).stdout
        )
        if verdict["verdict"] != "reproduced":
            raise SystemExit(f"unexpected verdict {verdict}")
        run([str(irp), "report", "--study", study, "--json"], env=env)
        run([str(irp), "verify", "--study", study, "--json"], env=env)
    print("package verified")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
