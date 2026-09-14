"""Inspection against an in-memory FastMCP server: no subprocess, no transport."""

import pytest
from fastmcp import Client, FastMCP

from mcp_servers_cli.inspection import inspect_server


@pytest.fixture
def server() -> FastMCP:
    mcp = FastMCP("Test")

    @mcp.tool
    def echo(text: str, times: int = 1) -> str:
        """Repeat text."""
        return text * times

    @mcp.resource("test://value")
    def value() -> str:
        """A resource."""
        return "42"

    @mcp.prompt
    def greet(name: str) -> str:
        """A prompt."""
        return f"Say hello to {name}"

    return mcp


async def test_tools_expose_their_parameters(server) -> None:
    async with Client(server) as client:
        info = await inspect_server(client)

    tool = info.tools[0]
    assert tool.name == "echo"
    assert tool.description == "Repeat text."
    assert [(p.name, p.type, p.required) for p in tool.parameters] == [
        ("text", "string", True),
        ("times", "integer", False),
    ]


async def test_resources_and_prompts_are_collected(server) -> None:
    async with Client(server) as client:
        info = await inspect_server(client)

    assert [r.uri for r in info.resources] == ["test://value"]
    assert info.prompts[0].name == "greet"
    assert info.prompts[0].arguments == ["name"]
