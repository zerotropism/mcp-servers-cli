"""The shipped config.json must stay loadable by the config transport."""

import json
from pathlib import Path

from mcp_servers_cli.transports import _expand_entry

CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def test_config_file_is_valid_json() -> None:
    config = json.loads(CONFIG.read_text())
    assert "mcpServers" in config


def test_every_entry_expands_to_a_usable_command(monkeypatch) -> None:
    """No placeholder must survive expansion, or the server is launched with a literal ${HOME}."""
    monkeypatch.setenv("HOME", "/home/testuser")
    servers = json.loads(CONFIG.read_text())["mcpServers"]

    for name, entry in servers.items():
        expanded = _expand_entry(entry)
        assert "${" not in json.dumps(expanded), name
        assert "command" in expanded or "url" in expanded, name
