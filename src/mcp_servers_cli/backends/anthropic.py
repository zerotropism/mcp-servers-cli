"""Anthropic backend: the Messages API. Optional dependency, `mcp-servers-cli[anthropic]`."""

from collections.abc import Sequence
from typing import Any

import anthropic
from anthropic.types import Message as AnthropicMessage

from mcp_servers_cli.llm import Message, ToolCall, ToolSpec

DEFAULT_MAX_TOKENS = 4096


def to_anthropic_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema or {"type": "object", "properties": {}},
    }


def to_anthropic_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    """Results go back in a user turn, each paired with its call by `tool_use_id`."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            blocks = [
                {
                    "type": "tool_result",
                    "tool_use_id": result.call_id,
                    "content": result.content,
                    "is_error": result.is_error,
                }
                for result in message.tool_results
            ]
            converted.append({"role": "user", "content": blocks})
        elif message.role == "assistant":
            blocks = [{"type": "text", "text": message.text}] if message.text else []
            blocks += [
                {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                for call in message.tool_calls
            ]
            converted.append({"role": "assistant", "content": blocks})
        else:
            converted.append({"role": "user", "content": message.text})
    return converted


def from_anthropic_message(message: AnthropicMessage) -> Message:
    text = "".join(block.text for block in message.content if block.type == "text")
    calls = tuple(
        ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
        for block in message.content
        if block.type == "tool_use"
    )
    return Message(role="assistant", text=text, tool_calls=calls)


class AnthropicBackend:
    """Reads ANTHROPIC_API_KEY from the environment, never from the command line."""

    def __init__(
        self,
        model: str,
        client: anthropic.AsyncAnthropic | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = client or anthropic.AsyncAnthropic()

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> Message:
        optional: dict[str, Any] = {}
        if system:
            optional["system"] = system
        if tools:
            optional["tools"] = [to_anthropic_tool(tool) for tool in tools]
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=to_anthropic_messages(messages),
            **optional,
        )
        return from_anthropic_message(response)
