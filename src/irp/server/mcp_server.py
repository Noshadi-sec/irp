"""MCP adapter: the catalog's tools over stdio, backed by the shared core.

Each tool's input schema is generated from its contract model and validated
strictly (unknown fields are rejected). Workflows run in a worker thread so
long runs never block the protocol loop.
"""

from __future__ import annotations

import inspect
import logging
from typing import Annotated, Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.tools import Tool
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import ConfigDict, Field

from irp.application.context import OperationContext
from irp.application.operations import execute
from irp.contracts.catalog import CATALOG, ToolContract
from irp.domain.errors import IRPError
from irp.identity import PRODUCT
from irp.server import delivery
from irp.server.prompts import register_prompts

INSTRUCTIONS = f"""{PRODUCT.display_name} turns a research paper into working code and proves, claim by claim, how close it gets.
You are the brain: read the paper, write the code, decide the runs. These tools act and keep the receipts.
Workflow: fetch_paper -> get_section / get_page_image -> add_claim for every claim -> write code in <study>/code
-> add_guess for missing details -> map_method -> create_env -> run (smallest faithful version first)
-> extract_metrics -> compare -> report. Use study_status to resume.
Hard rules: never type, estimate or copy a number as a result; never change the paper's method to make a run
succeed (record a guess); report 'could not run' with the blocking error; shortened runs never count; record
every claim before writing code; ask the person before any paid compute.
The {PRODUCT.skill_name} skill has the full workflow."""


def _signature(contract: ToolContract) -> inspect.Signature:
    """Build a keyword-only signature from the contract model so the SDK derives the same schema."""
    parameters = []
    for name, field in contract.input_model.model_fields.items():
        annotation: Any = Annotated[
            (field.annotation, *field.metadata, Field(description=field.description))
        ]
        default = (
            inspect.Parameter.empty
            if field.is_required()
            else field.get_default(call_default_factory=True)
        )
        parameters.append(
            inspect.Parameter(
                name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation
            )
        )
    return inspect.Signature(parameters, return_annotation=CallToolResult)


def _handler(contract: ToolContract, actor: str) -> Any:
    def call(arguments: dict[str, Any]) -> CallToolResult:
        try:
            result = execute(contract.name, arguments, OperationContext(actor=actor))
        except IRPError as error:
            return delivery.failure(error)
        except Exception as exc:  # noqa: BLE001 - every unexpected failure becomes a typed tool error
            return delivery.crash(contract.name, exc)
        image = result.get("path") if contract.returns_image else None
        return delivery.success(result, image_path=image)

    async def tool(**arguments: Any) -> CallToolResult:
        return await anyio.to_thread.run_sync(call, dict(arguments))

    tool.__name__ = contract.name
    tool.__doc__ = contract.description
    tool.__signature__ = _signature(contract)  # type: ignore[attr-defined]
    return tool


def build_tool(contract: ToolContract, actor: str = "mcp") -> Tool:
    tool = Tool.from_function(
        _handler(contract, actor),
        name=contract.name,
        title=contract.title,
        description=contract.description,
        annotations=ToolAnnotations(
            title=contract.title,
            read_only_hint=contract.read_only,
            destructive_hint=False,
            idempotent_hint=contract.read_only,
            open_world_hint=contract.open_world,
        ),
        structured_output=False,
    )
    base = tool.fn_metadata.arg_model

    class StrictArguments(base):  # type: ignore[valid-type, misc]
        model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    StrictArguments.__name__ = f"{contract.name}Arguments"
    tool.fn_metadata.arg_model = StrictArguments
    tool.parameters = StrictArguments.model_json_schema(by_alias=True)
    return tool


def create_server() -> MCPServer:
    server: MCPServer = MCPServer(
        name=PRODUCT.mcp_server_key,
        title=PRODUCT.display_name,
        description=PRODUCT.promise,
        instructions=INSTRUCTIONS,
        website_url=PRODUCT.repository,
        version=PRODUCT.version,
        tools=[build_tool(contract) for contract in CATALOG],
    )
    register_prompts(server)
    return server


def run_stdio() -> None:
    """Serve over stdio. Logs go to stderr only; stdout carries protocol messages."""
    from irp.logging_setup import configure_logging

    configure_logging(default_level="INFO")
    logging.getLogger("irp").info(
        "%s %s MCP server starting on stdio", PRODUCT.display_name, PRODUCT.version
    )
    create_server().run("stdio")
