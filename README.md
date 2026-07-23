# mcp-servers-cli

A generic command-line MCP client to **explore and test any MCP server** (Model Context Protocol): local servers (stdio), remote servers (HTTP/SSE), or servers described in a configuration file.

Built on top of [fastmcp](https://github.com/jlowin/fastmcp).

## Features

- Automatically lists the **tools**, **resources**, and **prompts** exposed by a server.
- **Interactive mode** to call a tool with JSON arguments or read a resource.
- Three connection modes: `stdio`, `http`, `config`.
- HTTP Bearer token authentication via the `MCP_TOKEN` environment variable.

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) (recommended)
- Optional: `npx` (Node.js) for third-party JS servers, `uvx` for Python ones

## Installation

```bash
uv sync
```

## Usage

```bash
uv run python mcp_tester.py <mode> <args...>
```

### `stdio` mode — local server launched as a subprocess

Pass the **full command** to run (quoted):

```bash
# Python server from a local project
uv run python mcp_tester.py stdio "uv run --directory ../my-server python server.py"

# Third-party Python server via uvx
uv run python mcp_tester.py stdio "uvx mcp-server-fetch"

# Third-party Node server via npx (e.g. the official filesystem server)
mkdir -p tmp
uv run python mcp_tester.py stdio "npx -y @modelcontextprotocol/server-filesystem $(pwd)/tmp"
```

> Tip: use `uv run --directory <folder>` (not `--project`) so that relative paths
> and the target server's environment are resolved correctly.

#### About the filesystem server sandbox

For `@modelcontextprotocol/server-filesystem`, the trailing argument is the
**allowed directory**: the server can only read/write/list files **inside** that
directory, and any path outside it is denied. Prefer scoping it to a dedicated
folder (e.g. `./tmp`) rather than your whole home or dev directory:

- Use an **absolute path** (`$(pwd)/tmp`), since the subprocess inherits the current working directory.
- The directory must **exist** before launch (`mkdir -p tmp`).
- Add `tmp/` to your `.gitignore` so test files aren't committed.

### `http` mode — remote server (HTTP/SSE)

```bash
# Streamable HTTP (default)
uv run python mcp_tester.py http https://example.com/mcp

# SSE (if the URL ends with /sse)
uv run python mcp_tester.py http https://example.com/sse
```

Token authentication (optional):

```bash
MCP_TOKEN=your_token uv run python mcp_tester.py http https://example.com/mcp
```

### `config` mode — configuration file

Same format as `claude_desktop_config.json`. Example `config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/absolute/path/to/tmp"]
    },
    "remote": {
      "url": "https://example.com/mcp"
    }
  }
}
```

```bash
uv run python mcp_tester.py config config.json filesystem
uv run python mcp_tester.py config config.json remote
```

This mode also accepts a per-server `"env": { ... }` block to pass secrets/API keys.
Note: JSON has no shell expansion, so use a full absolute path for the allowed directory.

## Interactive mode

Once connected, the tool lists the server's capabilities and then opens a prompt:

```
Commands: call <tool_name> <json_args> | read <resource_uri> | quit
```

Examples (against the filesystem server sandboxed to `./tmp`):

```
>> call list_directory {"path": "/absolute/path/to/tmp"}
>> call write_file {"path": "/absolute/path/to/tmp/hello.txt", "content": "hi"}
>> call read_text_file {"path": "/absolute/path/to/tmp/hello.txt"}
>> quit
```