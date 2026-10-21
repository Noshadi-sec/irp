"""Every place that names the version or the registry identity agrees.

Usage: python scripts/check_release_metadata.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    version_file = (REPO / "src" / "irp" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', version_file)
    version = match.group(1) if match else None
    manifest = json.loads((REPO / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]
    server = json.loads((REPO / "server.json").read_text(encoding="utf-8"))
    if manifest != version:
        problems.append(f".release-please-manifest.json has {manifest}, _version.py has {version}")
    if server["version"] != version or server["packages"][0]["version"] != version:
        problems.append(
            f"server.json versions {server['version']}/{server['packages'][0]['version']} != {version}"
        )
    if server["packages"][0]["identifier"] != "irp-agents":
        problems.append("server.json must publish the irp PyPI package")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    if f"mcp-name: {server['name']}" not in readme:
        problems.append(
            f"README.md must contain 'mcp-name: {server['name']}' for MCP Registry ownership checks"
        )
    for doc in ("installation.md", "client-configuration.md"):
        text = (REPO / "docs" / doc).read_text(encoding="utf-8")
        pinned = set(re.findall(r"irp-agents@(\d+\.\d+\.\d+)", text))
        if pinned and pinned != {version}:
            problems.append(f"docs/{doc} pins {sorted(pinned)}, expected {version}")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
