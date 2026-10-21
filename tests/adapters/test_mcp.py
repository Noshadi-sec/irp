"""The MCP adapter in-process: catalog, strict schemas, typed errors, images, prompts."""

import json

import anyio
import pytest
from mcp import Client

from irp.contracts.catalog import CATALOG
from irp.server.mcp_server import create_server
from tests.support.arxiv import TOY_PAPER


def run(coro):
    return anyio.run(coro)


def test_catalog_schemas_are_strict_and_complete():
    async def body():
        async with Client(create_server()) as client:
            return (await client.list_tools()).tools

    tools = run(body)
    assert [t.name for t in tools] == [c.name for c in CATALOG]
    for tool in tools:
        assert tool.input_schema["additionalProperties"] is False, tool.name
        assert "study" in tool.input_schema["required"], tool.name
    by_name = {t.name: t for t in tools}
    assert by_name["get_section"].annotations.read_only_hint is True
    assert by_name["run_remote"].annotations.open_world_hint is True
    specs = by_name["extract_metrics"].input_schema
    assert "specs" in specs["required"]


def test_workflow_results_and_errors(tmp_path):
    study = str(tmp_path / "study")

    async def body():
        async with Client(create_server()) as client:
            fetched = await client.call_tool(
                "fetch_paper", {"study": study, "paper": str(TOY_PAPER)}
            )
            section = await client.call_tool("get_section", {"study": study, "id": "eq:closed"})
            missing = await client.call_tool("get_section", {"study": study, "id": "nope"})
            refused = await client.call_tool(
                "run", {"study": study, "command": "true", "env": None}
            )
            extra = await client.call_tool("study_status", {"study": study, "unexpected": True})
            return fetched, section, missing, refused, extra

    fetched, section, missing, refused, extra = run(body)
    assert fetched.is_error is False
    assert fetched.structured_content["paper"]["source_format"] == "latex"
    assert json.loads(fetched.content[0].text) == fetched.structured_content
    assert "\\hat{w}" in section.structured_content["text"]
    assert missing.is_error and json.loads(missing.content[0].text)["error"]["code"] == "not_found"
    error = json.loads(refused.content[0].text)["error"]
    assert error["code"] == "rule_violation" and error["details"]["rule"] == 5
    assert extra.is_error


def test_page_image_returns_png_content(tmp_path):
    from tests.support.pdf import make_pdf

    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(make_pdf([["Title", "1 Introduction"]]))
    study = str(tmp_path / "study")

    async def body():
        async with Client(create_server()) as client:
            await client.call_tool("fetch_paper", {"study": study, "paper": str(pdf)})
            return await client.call_tool("get_page_image", {"study": study, "page": 1, "dpi": 50})

    result = run(body)
    assert [c.type for c in result.content] == ["text", "image"]
    assert result.content[1].mime_type == "image/png"


@pytest.mark.parametrize("prompt", ["build_paper", "resume_study"])
def test_prompts(prompt):
    async def body():
        async with Client(create_server()) as client:
            listed = [p.name for p in (await client.list_prompts()).prompts]
            args = (
                {"paper": "2501.00001", "study": "/tmp/s"}
                if prompt == "build_paper"
                else {"study": "/tmp/s"}
            )
            rendered = await client.get_prompt(prompt, args)
            return listed, rendered

    listed, rendered = run(body)
    assert prompt in listed
    assert "/tmp/s" in rendered.messages[0].content.text
