"""Provider-neutral conversation model. Backends translate it; nothing else knows an SDK."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool as the model sees it: the MCP name, description and JSON schema."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool the model asks for. `id` pairs it with its result, even where the API has none."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What the tool returned, as text, and whether it failed."""

    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Message:
    """One turn. A user turn has text, an assistant turn text or tool calls, a tool turn results."""

    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()


class LLMBackend(Protocol):
    """Anything that turns a conversation and a tool list into the next assistant turn."""

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> Message: ...
