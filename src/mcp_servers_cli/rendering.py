"""Turning inspection data and call results into terminal output."""

import json
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from mcp_servers_cli.inspection import ServerInfo

console = Console()


def _signature(parameters) -> str:
    return ", ".join(
        f"{p.name}: {p.type}" if p.required else f"[{p.name}: {p.type}]" for p in parameters
    )


def render_server(info: ServerInfo) -> None:
    """Print everything the server exposes, one table per capability."""
    tools = Table(title="Tools", title_justify="left")
    tools.add_column("name", style="bold")
    tools.add_column("arguments")
    tools.add_column("description", max_width=60)
    for tool in info.tools:
        tools.add_row(
            escape(tool.name),
            escape(_signature(tool.parameters)),
            escape(tool.description),
        )
    console.print(tools)
    if info.resources is None:
        console.print("Resources: not supported by this server")
    else:
        resources = Table(title="Resources", title_justify="left")
        resources.add_column("uri", style="bold")
        resources.add_column("description")
        for resource in info.resources:
            resources.add_row(escape(resource.uri), escape(resource.description or resource.name))
        console.print(resources)

    if info.prompts is None:
        console.print("Prompts: not supported by this server")
    else:
        prompts = Table(title="Prompts", title_justify="left")
        prompts.add_column("name", style="bold")
        prompts.add_column("arguments")
        prompts.add_column("description")
        for prompt in info.prompts:
            prompts.add_row(
                escape(prompt.name),
                escape(", ".join(prompt.arguments)),
                escape(prompt.description),
            )
        console.print(prompts)


def to_text(blocks: Any) -> list[str]:
    """Extract the text of MCP content blocks, whatever their concrete type."""
    return [block.text if hasattr(block, "text") else str(block) for block in blocks]


def render_blocks(blocks: Any) -> None:
    """Single renderer shared by tool calls and resource reads."""
    payload = json.dumps(to_text(blocks), indent=2, ensure_ascii=False)
    console.print(Syntax(payload, "json", theme="ansi_dark", background_color="default"))
