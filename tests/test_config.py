"""Smoke tests: config parsing and path expansion."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mcp_tester  # noqa: E402


def test_module_imports() -> None:
    assert hasattr(mcp_tester, "build_client")


def test_config_file_is_valid_json() -> None:
    config = json.loads((ROOT / "config.json").read_text())
    assert "mcpServers" in config
    assert "filesystem" in config["mcpServers"]


def test_env_vars_are_expanded() -> None:
    config = json.loads((ROOT / "config.json").read_text())
    args = config["mcpServers"]["filesystem"]["args"]
    expanded = [str(Path(os.path.expandvars(a)).expanduser()) for a in args]
    assert not any("${" in a for a in expanded)
    assert any(a.startswith("/") for a in expanded)
