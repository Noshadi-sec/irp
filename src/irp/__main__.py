"""Executable dispatcher: `irp mcp` serves MCP over stdio; everything else is the CLI.

MCP is routed before the CLI framework is imported, so the server starts fast
and nothing but protocol messages can reach stdout.
"""

from __future__ import annotations

import sys


def main() -> None:
    arguments = sys.argv[1:]
    if arguments == ["mcp"] or arguments == ["--mcp"]:
        from irp.server.mcp_server import run_stdio

        run_stdio()
        return
    from irp.cli.app import run_cli

    sys.exit(run_cli(arguments))


if __name__ == "__main__":
    main()
