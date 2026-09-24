"""The tool loop: the model asks, the MCP server answers, until the model replies in text.

The loop prints nothing. Callers observe it through two hooks, which is how the CLI renders
progress and how a trace can be recorded without touching the loop.
"""

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fastmcp import Client
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED

from mcp_servers_cli.llm import LLMBackend, Message, ToolCall, ToolResult, ToolSpec
from mcp_servers_cli.rendering import to_text

DEFAULT_MAX_STEPS = 10
MAX_RESULT_CHARS = 20_000

OnToolCall = Callable[[ToolCall], None]
OnToolResult = Callable[[ToolCall, ToolResult, float], None]


@dataclass(frozen=True, slots=True)
class AgentRun:
    """How a run ended. `stopped` means the step budget ran out before a text answer."""

    answer: str
    messages: list[Message]
    steps: int
    stopped: bool


def tool_specs(tools: Sequence[Any]) -> list[ToolSpec]:
    """MCP tools as the model sees them."""
    return [
        ToolSpec(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.input_schema or {"type": "object", "properties": {}},
        )
        for tool in tools
    ]


def sanitize_args(args: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    """Drop arguments the schema does not declare, which models sometimes invent.

    A schema without `properties`, or one that allows additional properties, is left alone.
    """
    properties = schema.get("properties")
    if not properties or schema.get("additionalProperties") is True:
        return dict(args)
    return {key: value for key, value in args.items() if key in properties}


def result_text(result: Any) -> str:
    """The text a model reads back: content blocks first, structured content as a fallback."""
    text = "\n".join(to_text(result.content))
    if not text and result.structured_content is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    if len(text) > MAX_RESULT_CHARS:
        text = f"{text[:MAX_RESULT_CHARS]}\n[truncated: {len(text)} characters in total]"
    return text


async def execute(client: Client, call: ToolCall, schemas: Mapping[str, Mapping]) -> ToolResult:
    """Run one call. Every failure a model can recover from comes back as an error result."""
    if call.name not in schemas:
        available = ", ".join(sorted(schemas))
        return ToolResult(
            call.id, call.name, f"unknown tool '{call.name}'; available: {available}", True
        )
    arguments = sanitize_args(call.arguments, schemas[call.name])
    try:
        result = await client.call_tool(call.name, arguments, raise_on_error=False)
    except MCPError as exc:
        if exc.code == CONNECTION_CLOSED:
            raise
        return ToolResult(call.id, call.name, str(exc), True)
    return ToolResult(call.id, call.name, result_text(result), result.is_error)


async def first_turn(
    client: Client, backend: LLMBackend, prompt: str, *, system: str = ""
) -> Message:
    """One model turn with the server's tools and nothing executed: what the model would do."""
    specs = tool_specs(await client.list_tools())
    return await backend.complete(system, [Message("user", prompt)], specs)


async def run_agent(
    client: Client,
    backend: LLMBackend,
    prompt: str,
    *,
    system: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    on_tool_call: OnToolCall | None = None,
    on_tool_result: OnToolResult | None = None,
) -> AgentRun:
    """Alternate model turns and tool calls until the model answers or the budget runs out."""
    specs = tool_specs(await client.list_tools())
    schemas = {spec.name: spec.input_schema for spec in specs}
    messages = [Message("user", prompt)]

    for step in range(1, max_steps + 1):
        reply = await backend.complete(system, messages, specs)
        messages.append(reply)
        if not reply.tool_calls:
            return AgentRun(reply.text, messages, step, stopped=False)

        results = []
        for call in reply.tool_calls:
            if on_tool_call:
                on_tool_call(call)
            started = time.perf_counter()
            result = await execute(client, call, schemas)
            if on_tool_result:
                on_tool_result(call, result, time.perf_counter() - started)
            results.append(result)
        messages.append(Message("tool", tool_results=tuple(results)))

    return AgentRun("", messages, max_steps, stopped=True)
