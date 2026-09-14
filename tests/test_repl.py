"""REPL argument parsing: the loop must reject what a paste should never produce."""

import pytest

from mcp_servers_cli.repl import MAX_ARGUMENT_LENGTH, _arguments


def test_object_arguments_are_accepted() -> None:
    assert _arguments('{"a": 1}') == {"a": 1}


def test_non_object_arguments_are_refused() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _arguments("[1, 2, 3]")


def test_oversized_arguments_are_refused() -> None:
    with pytest.raises(ValueError, match="refused"):
        _arguments("{" + " " * MAX_ARGUMENT_LENGTH + "}")
