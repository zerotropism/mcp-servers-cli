"""Building a Client for each supported transport."""

import json
import os
import shlex
from collections.abc import Callable
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

TOKEN_ENV_VAR = "MCP_TOKEN"


class UnknownServerError(LookupError):
    """The requested server name is not in the config file."""


def expand(token: str) -> str:
    """Expand $VARS and a leading ~ in one token. Flags and plain words pass through."""
    expanded = os.path.expandvars(token)
    if expanded.startswith("~"):
        return str(Path(expanded).expanduser())
    return expanded


def stdio_client(command: str, env: dict[str, str] | None = None) -> Client:
    """Run a server as a subprocess.

    The MCP SDK only forwards a whitelist of environment variables to that subprocess
    (HOME, LOGNAME, PATH, SHELL, TERM, USER), so anything the server needs must be
    passed explicitly through `env`.
    """
    parts = [expand(token) for token in shlex.split(command)]
    if not parts:
        raise ValueError("Empty stdio command")
    return Client(StdioTransport(command=parts[0], args=parts[1:], env=env))


def http_client(url: str) -> Client:
    """Connect to a remote server. MCP_TOKEN, when set, is sent as a bearer token."""
    token = os.environ.get(TOKEN_ENV_VAR)
    if token:
        return Client(StreamableHttpTransport(url, headers={"Authorization": f"Bearer {token}"}))
    return Client(url)


def _expand_entry(entry: dict) -> dict:
    """Expand the command and every argument of one config entry."""
    expanded = dict(entry)
    if "command" in expanded:
        expanded["command"] = expand(expanded["command"])
    if "args" in expanded:
        expanded["args"] = [expand(arg) for arg in expanded["args"]]
    return expanded


def config_client(config_path: str | Path, server_name: str) -> Client:
    """Connect to a server declared in a claude_desktop_config.json-style file."""
    config = json.loads(Path(config_path).read_text())
    servers = config.get("mcpServers", config)
    if server_name not in servers:
        raise UnknownServerError(f"Server '{server_name}' not found. Available: {sorted(servers)}")
    return Client({"mcpServers": {server_name: _expand_entry(servers[server_name])}})


# Adding a transport means adding a builder here, not editing the ones above
BUILDERS: dict[str, Callable[..., Client]] = {
    "stdio": stdio_client,
    "http": http_client,
    "config": config_client,
}
