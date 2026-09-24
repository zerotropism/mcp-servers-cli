"""Turning a failure into the one line a terminal user needs. The full trace stays opt-in."""

import json

from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED

DEBUG_ENV_VAR = "MCP_SERVERS_CLI_DEBUG"


def leaf(exc: BaseException) -> BaseException:
    """First innermost exception of nested exception groups, as raised by anyio task groups."""
    seen: set[int] = set()
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions and id(exc) not in seen:
        seen.add(id(exc))
        exc = exc.exceptions[0]
    return exc


def describe(exc: BaseException) -> str:
    """One line naming the cause, without the stack."""
    exc = leaf(exc)
    if isinstance(exc, MCPError) and exc.code == CONNECTION_CLOSED:
        return (
            "the server closed the connection: its own error output above gives the cause "
            "(hidden if --quiet was given)"
        )
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON: {exc}"
    return str(exc) or type(exc).__name__
