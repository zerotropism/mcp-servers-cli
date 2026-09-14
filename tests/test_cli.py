"""Target resolution: the CLI must refuse ambiguous or incomplete transports."""

import pytest

from mcp_servers_cli.cli import build_client


def test_exactly_one_transport_is_required() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build_client(None, None, None, None, None)


def test_two_transports_are_refused() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build_client("uv run server", "https://example.com/mcp", None, None, None)


def test_config_without_server_is_refused() -> None:
    with pytest.raises(ValueError, match="--server"):
        build_client(None, None, "config.json", None, None)


def test_env_pairs_reach_the_transport(monkeypatch) -> None:
    """The MCP SDK drops unlisted variables, so --env is the only way to configure a server."""
    captured = {}

    def fake_stdio(command, env=None, log_file=None):
        captured.update(env=env, log_file=log_file)
        return object()

    monkeypatch.setattr("mcp_servers_cli.cli.stdio_client", fake_stdio)
    build_client("uv run server", None, None, None, ["A=1", "B=2"])
    assert captured["env"] == {"A": "1", "B": "2"}
    assert captured["log_file"] is None


def test_quiet_redirects_the_subprocess_stderr(monkeypatch) -> None:
    captured = {}

    def fake_stdio(command, env=None, log_file=None):
        captured["log_file"] = log_file
        return object()

    monkeypatch.setattr("mcp_servers_cli.cli.stdio_client", fake_stdio)
    build_client("uv run server", None, None, None, None, quiet=True)
    assert captured["log_file"] is not None
