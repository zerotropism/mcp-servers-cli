"""A one-tool stdio server for the end-to-end agent test."""

from fastmcp import FastMCP

mcp = FastMCP("Add")


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run(show_banner=False)
