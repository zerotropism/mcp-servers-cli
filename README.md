# mcp-servers-cli

Inspect, call and drive any MCP server from the command line. Point it at a local process, a
remote HTTP endpoint, or an entry in a `claude_desktop_config.json`-style file, and it lists the
tools, resources and prompts the server exposes — then lets you exercise them.

## Installation

```bash
uv sync
uv run mcp-servers-cli --help
```

Or without cloning, once published:

```bash
uvx mcp-servers-cli inspect --stdio "uvx mcp-server-fetch"
```

## Commands

Every command takes exactly one target: `--stdio`, `--http` or `--config` with `--server`.

```bash
# What does this server expose?
mcp-servers-cli inspect --stdio "uv run server.py"
mcp-servers-cli inspect --http https://example.com/mcp
mcp-servers-cli inspect --config config.json --server fetch

# Call one tool
mcp-servers-cli call fetch '{"url": "https://example.com"}' --stdio "uvx mcp-server-fetch"

# Read one resource
mcp-servers-cli read "tasks://stats" --stdio "uv run server.py"

# Inspect, then stay interactive
mcp-servers-cli repl --stdio "uv run server.py"
```

Inside the REPL: `call <tool> <json>`, `read <uri>`, `list`, `quit`.

## Configuring the server you launch

A stdio server runs as a subprocess, and the MCP SDK forwards only a whitelist of environment
variables to it — `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, `USER`. Anything else the server
reads from its environment is silently absent, and it falls back to its defaults.

`--env` is how you pass the rest:

```bash
mcp-servers-cli call add_task '{"title": "buy milk"}' \
  --env TASK_BACKEND=sqlite --env DB_PATH=tasks.db \
  --stdio "uv run --directory ../mcpserver-template mcpserver-template"
```

`~` and `$VARS` are expanded in the command and in every argument, including entries read from
a config file.

For a remote server, `MCP_TOKEN` is sent as a bearer token when set.

## Noisy servers

A stdio server writes its own logs to stderr, and they land in your terminal. Servers built on
older MCP SDKs answer FastMCP's capability probe with a wall of validation errors before falling
back to the legacy protocol — the inspection still succeeds, but the output is buried.

`--quiet` discards that stream. It is not the default on purpose: when a server fails to start,
the reason is in its first stderr line, and hiding it turns a clear error into a bare
"Connection closed".

## Errors

A failure prints one line naming its cause and exits with status 1:

```
error: Client failed to connect: [Errno 2] No such file or directory: 'uvx'
```

When a stdio server dies while starting, its own stderr line comes first and the error line points
to it. Set `MCP_SERVERS_CLI_DEBUG=1` to get the full traceback instead.

## Configuration file

The `--config` mode reads the `mcpServers` format used by Claude Desktop:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${HOME}/Developer"]
    },
    "fetch": { "command": "uvx", "args": ["mcp-server-fetch"] },
    "remote": { "url": "https://example.com/mcp" }
  }
}
```

## Project structure

```
src/mcp_servers_cli/
├── transports.py   one builder per transport, plus path expansion
├── inspection.py   reads a server into dataclasses
├── rendering.py    turns those dataclasses into tables
├── repl.py         interactive loop over a connected client
├── errors.py       turns a failure into one line
├── llm.py          provider-neutral conversation model and the LLMBackend protocol
├── backends/       one module per provider, translating to and from that model
└── cli.py          cyclopts commands
```

Inspection returns data and never prints; rendering never talks to a server. That is what lets
the tests run an in-memory FastMCP server and assert on structures rather than on captured
stdout.

Adding a transport means adding a builder in `transports.py` and a target option in `cli.py`,
without touching the existing ones.

Only `backends/` imports an LLM SDK; everything else works on the neutral types of `llm.py`.
Adding a provider means adding one module there and one line in `backends/__init__.py`.

## Tests

```bash
uv run pytest
```

No network and no server process: the inspection tests run against an in-memory FastMCP server,
the transport tests check expansion rules, the rendering tests capture a rich console, and the
error tests launch a command that does not exist. The backend tests translate real SDK objects
through a stand-in client: neither Ollama nor an API key is needed.

## Dependencies

| Package    | Role                                  |
|------------|---------------------------------------|
| `fastmcp`  | MCP client and transports             |
| `cyclopts` | Commands and help, from type hints    |
| `rich`     | Tables and JSON highlighting          |
| `ollama`   | Local models, the default backend     |
| `anthropic` | Anthropic backend, optional: `mcp-servers-cli[anthropic]` |

`cyclopts` and `rich` already ship in FastMCP's dependency tree; they are declared explicitly
rather than relied on transitively.
