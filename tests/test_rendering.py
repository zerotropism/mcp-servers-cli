"""Rendering must produce output for every capability, and never eat server text."""

import pytest
from rich.console import Console

from mcp_servers_cli import rendering
from mcp_servers_cli.inspection import (
    Parameter,
    PromptInfo,
    ResourceInfo,
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
