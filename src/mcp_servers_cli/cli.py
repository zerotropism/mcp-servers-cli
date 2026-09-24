"""Command line entry point. One command per action, the target given as an option."""

import json
import os
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Group, Parameter
from fastmcp import Client
from rich.console import Console
from rich.markup import escape

from mcp_servers_cli.agent import DEFAULT_MAX_STEPS, run_agent
from mcp_servers_cli.backends import BACKENDS, create_backend
from mcp_servers_cli.errors import DEBUG_ENV_VAR, describe
from mcp_servers_cli.inspection import inspect_server
from mcp_servers_cli.rendering import (
    render_answer,
    render_blocks,
    render_server,
    render_tool_call,
    render_tool_result,
)
from mcp_servers_cli.repl import run_repl
from mcp_servers_cli.transports import config_client, http_client, stdio_client

app = App(
    name="mcp-servers-cli",
    help="Inspect, call and drive any MCP server.",
    version="0.1.0",
)

TARGET = Group("Target", help="Exactly one transport must be given.")

Stdio = Annotated[str | None, Parameter(group=TARGET, help="Command launching the server.")]
Http = Annotated[str | None, Parameter(group=TARGET, help="URL of a remote server.")]
Config = Annotated[str | None, Parameter(group=TARGET, help="Path to an mcpServers JSON file.")]
Server = Annotated[str | None, Parameter(group=TARGET, help="Server name inside --config.")]
Env = Annotated[list[str] | None, Parameter(help="KEY=VALUE passed to a stdio subprocess.")]
Quiet = Annotated[bool, Parameter(help="Hide the inspected server's own stderr output.")]


def build_client(
    stdio: str | None,
    http: str | None,
    config: str | None,
    server: str | None,
    env: list[str] | None,
    quiet: bool = False,
) -> Client:
    """Resolve the mutually exclusive target options into a Client."""
    chosen = [
        name for name, value in (("stdio", stdio), ("http", http), ("config", config)) if value
    ]
    if len(chosen) != 1:
        raise ValueError("Give exactly one of --stdio, --http or --config.")

    if stdio:
        return stdio_client(
            stdio,
            env=dict(item.split("=", 1) for item in env) if env else None,
            log_file=Path(os.devnull) if quiet else None,
        )
    if http:
        return http_client(http)
    if not server:
        raise ValueError("--config requires --server.")
    return config_client(config, server)


@app.command
async def inspect(
    *,
    stdio: Stdio = None,
    http: Http = None,
    config: Config = None,
    server: Server = None,
    env: Env = None,
    quiet: Quiet = False,
) -> None:
    """List the tools, resources and prompts a server exposes."""
    async with build_client(stdio, http, config, server, env, quiet) as client:
        render_server(await inspect_server(client))


@app.command
async def call(
    tool: str,
    arguments: str = "{}",
    *,
    stdio: Stdio = None,
    http: Http = None,
    config: Config = None,
    server: Server = None,
    env: Env = None,
    quiet: Quiet = False,
) -> None:
    """Call one tool with JSON arguments and print the result."""
    async with build_client(stdio, http, config, server, env, quiet) as client:
        result = await client.call_tool(tool, json.loads(arguments))
        render_blocks(result.content)


@app.command
async def read(
    uri: str,
    *,
    stdio: Stdio = None,
    http: Http = None,
    config: Config = None,
    server: Server = None,
    env: Env = None,
    quiet: Quiet = False,
) -> None:
    """Read one resource and print its content."""
    async with build_client(stdio, http, config, server, env, quiet) as client:
        render_blocks(await client.read_resource(uri))


@app.command
async def repl(
    *,
    stdio: Stdio = None,
    http: Http = None,
    config: Config = None,
    server: Server = None,
    env: Env = None,
    quiet: Quiet = False,
) -> None:
    """Inspect a server, then take commands interactively."""
    async with build_client(stdio, http, config, server, env, quiet) as client:
        render_server(await inspect_server(client))
        await run_repl(client)


@app.command
async def agent(
    prompt: str,
    *,
    model: Annotated[str, Parameter(help="Model name, e.g. qwen3.5:4b or claude-sonnet-5.")],
    backend: Annotated[
        str, Parameter(help=f"LLM backend: {', '.join(sorted(BACKENDS))}.")
    ] = "ollama",
    system: Annotated[str, Parameter(help="System prompt given to the model.")] = "",
    max_steps: Annotated[int, Parameter(help="Model turns allowed before giving up.")] = (
        DEFAULT_MAX_STEPS
    ),
    stdio: Stdio = None,
    http: Http = None,
    config: Config = None,
    server: Server = None,
    env: Env = None,
    quiet: Quiet = False,
) -> None:
    """Let a model use the server's tools to answer a prompt."""
    llm = create_backend(backend, model)
    async with build_client(stdio, http, config, server, env, quiet) as client:
        run = await run_agent(
            client,
            llm,
            prompt,
            system=system,
            max_steps=max_steps,
            on_tool_call=render_tool_call,
            on_tool_result=render_tool_result,
        )
    if run.stopped:
        raise RuntimeError(f"no final answer after {max_steps} model turns (see --max-steps)")
    render_answer(run.answer)


def main(tokens: list[str] | None = None) -> None:
    """Console entry point: one line per failure, the full trace when the debug variable is set."""
    try:
        app(tokens)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        if os.environ.get(DEBUG_ENV_VAR):
            raise
        Console(stderr=True, soft_wrap=True).print(f"[red]error:[/red] {escape(describe(exc))}")
        sys.exit(1)
