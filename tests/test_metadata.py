"""The version shown to users is the one PyPI receives: pyproject.toml is its only source."""

from importlib import metadata

import pytest

from mcp_servers_cli.cli import main


def test_version_comes_from_the_package_metadata(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.strip() == metadata.version("mcp-servers-cli")
