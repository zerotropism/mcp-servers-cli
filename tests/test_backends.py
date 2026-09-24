"""Backend selection: known names, optional SDKs, one clear message when one is missing."""

import sys

import pytest

from mcp_servers_cli.backends import create_backend


def test_unknown_backend_lists_the_available_ones() -> None:
    with pytest.raises(ValueError, match="anthropic.*ollama"):
        create_backend("gpt", "some-model")


def test_ollama_backend_carries_the_model() -> None:
    assert create_backend("ollama", "qwen3.5:4b").model == "qwen3.5:4b"


def test_anthropic_backend_reads_the_key_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert create_backend("anthropic", "claude-test").model == "claude-test"


def test_missing_optional_sdk_names_the_extra(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.delitem(sys.modules, "mcp_servers_cli.backends.anthropic", raising=False)
    with pytest.raises(ModuleNotFoundError, match=r"mcp-servers-cli\[anthropic\]"):
        create_backend("anthropic", "claude-test")
