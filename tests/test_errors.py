"""Failures reach the terminal as one line naming the cause."""

import json

import pytest
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED

from mcp_servers_cli.cli import main
from mcp_servers_cli.errors import DEBUG_ENV_VAR, describe, leaf


def test_leaf_unwraps_nested_groups() -> None:
    cause = RuntimeError("Client failed to connect: All connection attempts failed")
    nested = ExceptionGroup("outer", [ExceptionGroup("inner", [cause])])
    assert leaf(nested) is cause


def test_closed_connection_points_to_the_server_output() -> None:
    message = describe(MCPError(code=CONNECTION_CLOSED, message="Connection closed"))
    assert "closed the connection" in message
    assert "--quiet" in message


def test_invalid_json_is_named() -> None:
    try:
        json.loads("not json")
    except json.JSONDecodeError as exc:
        assert describe(exc).startswith("invalid JSON:")


def test_missing_command_fails_in_one_line(capsys, monkeypatch) -> None:
    """The open point from 3.4: a missing command used to print 159 lines."""
    monkeypatch.delenv(DEBUG_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exit_info:
        main(["inspect", "--stdio", "mcp-servers-cli-missing-command", "--quiet"])
    assert exit_info.value.code == 1
    lines = capsys.readouterr().err.strip().splitlines()
    assert lines == [
        "error: Client failed to connect: [Errno 2] No such file or directory: "
        "'mcp-servers-cli-missing-command'"
    ]


def test_debug_variable_keeps_the_traceback(monkeypatch) -> None:
    monkeypatch.setenv(DEBUG_ENV_VAR, "1")
    with pytest.raises(BaseException) as exc_info:
        main(["inspect", "--stdio", "mcp-servers-cli-missing-command", "--quiet"])
    assert not isinstance(exc_info.value, SystemExit)
