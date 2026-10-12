"""Rendering must produce output for every capability, and never eat server text."""

import json

import pytest
from fastmcp import Client, FastMCP
from mcp.types import TextContent
from pydantic import BaseModel
from rich.console import Console

from mcp_servers_cli import rendering
from mcp_servers_cli.inspection import (
    Parameter,
    PromptInfo,
    ResourceInfo,
    ResourceTemplateInfo,
    ServerInfo,
    ToolInfo,
)

INFO = ServerInfo(
    tools=[
        ToolInfo(
            name="fetch",
            description="Fetch a URL.",
            parameters=[
                Parameter("url", "string", True),
                Parameter("max_length", "integer", False),
            ],
        )
    ],
    resources=[ResourceInfo(uri="test://value", name="value", description="A value.")],
    prompts=[PromptInfo(name="greet", description="Say hello.", arguments=["name"])],
)


@pytest.fixture
def captured(monkeypatch) -> Console:
    console = Console(record=True, width=200)
    monkeypatch.setattr(rendering, "console", console)
    return console


def test_every_capability_is_printed(captured) -> None:
    rendering.render_server(INFO)
    output = captured.export_text()

    assert "fetch" in output
    assert "test://value" in output
    assert "greet" in output


def test_optional_parameters_survive_rich_markup(captured) -> None:
    """Square brackets are rich markup: unescaped, the optional arguments vanish."""
    rendering.render_server(INFO)
    output = captured.export_text()

    assert "url: string" in output
    assert "max_length: integer" in output


def test_unsupported_capabilities_are_stated(captured) -> None:
    rendering.render_server(ServerInfo(tools=[], resources=None, prompts=None))
    output = captured.export_text()

    assert "Resources: not supported" in output
    assert "Prompts: not supported" in output


def test_resource_templates_get_their_own_table(captured) -> None:
    template = ResourceTemplateInfo("report://{path}", "report", "A report.")
    rendering.render_server(
        ServerInfo(tools=[], resources=[], prompts=[], resource_templates=[template])
    )
    output = captured.export_text()

    assert "Resource templates" in output
    assert "report://{path}" in output


def text(value: str) -> TextContent:
    return TextContent(type="text", text=value)


def test_a_json_text_block_is_shown_as_json() -> None:
    assert rendering.block_values([text('{"a": [1, 2]}')]) == {"a": [1, 2]}


def test_plain_text_blocks_stay_text() -> None:
    assert rendering.block_values([text("hello")]) == "hello"
    assert rendering.block_values([text("one"), text("2")]) == ["one", 2]


class Source(BaseModel):
    ip: str
    errors: int


@pytest.fixture
def results_server() -> FastMCP:
    mcp = FastMCP("Results")

    @mcp.tool
    def sources() -> list[Source]:
        return [Source(ip="10.0.0.1", errors=8)]

    @mcp.tool
    def counts() -> dict[str, int]:
        return {"alice": 3}

    @mcp.tool
    def untyped():
        return "free text"

    return mcp


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("sources", [{"ip": "10.0.0.1", "errors": 8}]),
        ("counts", {"alice": 3}),
        ("untyped", "free text"),
    ],
)
async def test_results_are_shown_as_returned_without_the_mcp_wrapper(
    results_server, tool, expected
) -> None:
    async with Client(results_server) as client:
        result = await client.call_tool(tool, {})
    assert rendering.result_value(result) == expected


LONG = "The CV matches the job description well, with experience in secure network services"


def terminal(monkeypatch, is_terminal: bool) -> Console:
    console = Console(record=True, width=40, force_terminal=is_terminal)
    monkeypatch.setattr(rendering, "console", console)
    return console


def test_long_values_wrap_in_a_terminal_instead_of_being_cut(monkeypatch) -> None:
    console = terminal(monkeypatch, True)
    rendering.render_json({"explanation": LONG})
    assert "secure network services" in " ".join(console.export_text().split())


def test_piped_output_is_valid_json(monkeypatch) -> None:
    console = terminal(monkeypatch, False)
    rendering.render_json([{"explanation": LONG}])
    assert json.loads(console.export_text()) == [{"explanation": LONG}]


def test_text_is_printed_as_text_not_as_a_json_string(monkeypatch) -> None:
    console = terminal(monkeypatch, True)
    rendering.render_blocks([text("NETWORK ENGINEER\nBuild [and] operate")])
    assert console.export_text() == "NETWORK ENGINEER\nBuild [and] operate\n"
