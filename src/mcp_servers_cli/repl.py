"""Interactive loop over a connected client."""

import json

from fastmcp import Client

from mcp_servers_cli.inspection import inspect_server
from mcp_servers_cli.rendering import console, render_blocks, render_server

MAX_ARGUMENT_LENGTH = 100_000
HELP = "Commands: call <tool> <json> | read <uri> | list | quit"


def _arguments(raw: str) -> dict:
    """Parse JSON arguments, refusing anything a terminal paste should never produce."""
    if len(raw) > MAX_ARGUMENT_LENGTH:
        raise ValueError(f"Arguments longer than {MAX_ARGUMENT_LENGTH} characters are refused.")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return parsed


async def run_repl(client: Client) -> None:
    """Read commands until EOF or quit. The client must already be connected."""
    console.print(HELP)

    while True:
        try:
            line = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not line or line == "quit":
            return

        parts = line.split(maxsplit=2)
        action = parts[0]

        try:
            if action == "list":
                render_server(await inspect_server(client))
            elif action == "call" and len(parts) >= 2:
                result = await client.call_tool(
                    parts[1], _arguments(parts[2] if len(parts) > 2 else "{}")
                )
                render_blocks(result.content)
            elif action == "read" and len(parts) >= 2:
                render_blocks(await client.read_resource(parts[1]))
            else:
                console.print(HELP)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Invalid JSON:[/red] {exc}")
        except Exception as exc:  # noqa: BLE001 - a REPL must survive any server-side failure
            console.print(f"[red]{type(exc).__name__}:[/red] {exc}")
