"""Transport construction: expansion rules and config lookup. No server involved."""

import json

import pytest

from mcp_servers_cli.transports import (
    UnknownServerError,
    _expand_entry,
    config_client,
    expand,
    stdio_client,
)


def test_tilde_is_expanded(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/home/testuser")
    assert expand("~/Developer") == "/home/testuser/Developer"


def test_environment_variables_are_expanded(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/home/testuser")
    assert expand("${HOME}/Developer") == "/home/testuser/Developer"


@pytest.mark.parametrize("token", ["--directory", "", "mcp-server-fetch", "$UNSET_VAR/x"])
def test_plain_tokens_pass_through(token: str) -> None:
    """Flags, empty strings and unset variables must not become paths."""
    assert expand(token) == token


def test_stdio_command_is_expanded(monkeypatch) -> None:
    """The bug this fixes: a ~ in the command silently became a missing directory."""
    monkeypatch.setenv("HOME", "/home/testuser")
    entry = _expand_entry({"command": "uv", "args": ["run", "--directory", "~/x", "server"]})
    assert entry["args"] == ["run", "--directory", "/home/testuser/x", "server"]


def test_empty_command_is_rejected() -> None:
    with pytest.raises(ValueError):
        stdio_client("   ")


def test_unknown_server_lists_the_available_ones(tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"mcpServers": {"fetch": {"command": "uvx"}}}))
    with pytest.raises(UnknownServerError, match="fetch"):
        config_client(config, "nope")
