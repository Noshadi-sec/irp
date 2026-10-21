"""Project workflow results and typed errors onto MCP tool results.

Success: the complete result as structured content plus the same JSON as text.
Failure: `isError: true` and the canonical `{"error": ...}` diagnostic as text,
so the agent reads the code, remediation and details instead of prose.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from mcp_types import CallToolResult, ImageContent, TextContent

from irp.domain.errors import ErrorCode, IRPError

logger = logging.getLogger("irp.mcp")


def _text(payload: Any) -> TextContent:
    return TextContent(
        type="text", text=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def success(result: dict[str, Any], *, image_path: str | None = None) -> CallToolResult:
    content: list[Any] = [_text(result)]
    if image_path is not None:
        data = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        content.append(ImageContent(type="image", data=data, mime_type="image/png"))
    return CallToolResult(content=content, structured_content=result)


def failure(error: IRPError) -> CallToolResult:
    return CallToolResult(content=[_text({"error": error.to_dict()})], is_error=True)


def crash(tool: str, exc: BaseException) -> CallToolResult:
    """An unexpected failure: logged with its traceback on stderr, reported without guessing a cause."""
    logger.exception("Tool %s failed unexpectedly", tool)
    error = IRPError(
        ErrorCode.EXECUTION_FAILURE,
        f"{tool} failed unexpectedly: {type(exc).__name__}: {exc}",
        remediation="Retry once. If it fails again, run `irp doctor` and open an issue with the "
        "doctor output and this message.",
    )
    return failure(error)
