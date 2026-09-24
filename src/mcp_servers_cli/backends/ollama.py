"""Ollama backend: local models through the official async client."""

from collections.abc import Mapping, Sequence
from typing import Any

import ollama

from mcp_servers_cli.llm import Message, ToolCall, ToolSpec

SCHEMA_KEYS = {"type", "value", "description"}


def normalize_args(args: Mapping[str, Any]) -> dict[str, Any]:
    """Unwrap values some local models wrap in their schema: {'type': 'string', 'value': 'x'}.

    Only dicts made of schema keys are unwrapped, so a genuine nested object is left intact.
    """
    return {
        key: value["value"]
        if isinstance(value, dict) and "value" in value and set(value) <= SCHEMA_KEYS
        else value
        for key, value in args.items()
    }


def to_ollama_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


def to_ollama_messages(system: str, messages: Sequence[Message]) -> list[dict[str, Any]]:
    """Ollama pairs a result with its call by position: one tool message per result, in order."""
    converted: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for message in messages:
        if message.role == "tool":
            converted.extend(
                {
                    "role": "tool",
                    "tool_name": result.name,
                    "content": f"error: {result.content}" if result.is_error else result.content,
                }
                for result in message.tool_results
            )
        elif message.tool_calls:
            converted.append(
                {
                    "role": "assistant",
                    "content": message.text,
                    "tool_calls": [
                        {"function": {"name": call.name, "arguments": call.arguments}}
                        for call in message.tool_calls
                    ],
                }
            )
        else:
            converted.append({"role": message.role, "content": message.text})
    return converted


def from_ollama_message(message: ollama.Message) -> Message:
    """Ollama calls carry no id: number them so their results can be paired back."""
    calls = tuple(
        ToolCall(
            id=f"call_{index}",
            name=call.function.name,
            arguments=normalize_args(call.function.arguments or {}),
        )
        for index, call in enumerate(message.tool_calls or [])
    )
    return Message(role="assistant", text=message.content or "", tool_calls=calls)


class OllamaBackend:
    """Talks to the Ollama server named by OLLAMA_HOST, localhost by default."""

    def __init__(self, model: str, client: ollama.AsyncClient | None = None) -> None:
        self.model = model
        self._client = client or ollama.AsyncClient()

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> Message:
        response = await self._client.chat(
            model=self.model,
            messages=to_ollama_messages(system, messages),
            tools=[to_ollama_tool(tool) for tool in tools],
        )
        return from_ollama_message(response.message)
