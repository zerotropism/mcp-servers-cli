"""Anthropic translation, checked against the SDK's own types rather than hand-written dicts."""

from anthropic.types import Message as AnthropicMessage
from anthropic.types import TextBlock, ToolUseBlock

from mcp_servers_cli.backends.anthropic import (
    AnthropicBackend,
    from_anthropic_message,
    to_anthropic_messages,
    to_anthropic_tool,
)
from mcp_servers_cli.llm import Message, ToolCall, ToolResult, ToolSpec

TOOL = ToolSpec("add", "Add a number", {"type": "object", "properties": {"a": {"type": "integer"}}})


def _response(*blocks) -> AnthropicMessage:
    return AnthropicMessage(
        id="msg_1",
        content=list(blocks),
        model="claude-test",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage={"input_tokens": 1, "output_tokens": 1},
    )


def test_tool_uses_input_schema() -> None:
    assert to_anthropic_tool(TOOL)["input_schema"] == TOOL.input_schema


def test_response_keeps_text_and_call_ids() -> None:
    message = from_anthropic_message(
        _response(
            TextBlock(type="text", text="Adding."),
            ToolUseBlock(type="tool_use", id="toolu_1", name="add", input={"a": 1}),
        )
    )
    assert message == Message(
        "assistant", "Adding.", tool_calls=(ToolCall("toolu_1", "add", {"a": 1}),)
    )


def test_results_go_back_in_a_user_turn_paired_by_id() -> None:
    history = [
        Message("user", "add one"),
        Message("assistant", tool_calls=(ToolCall("toolu_1", "add", {"a": 1}),)),
        Message("tool", tool_results=(ToolResult("toolu_1", "add", "boom", is_error=True),)),
    ]
    converted = to_anthropic_messages(history)
    assert converted[1] == {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "toolu_1", "name": "add", "input": {"a": 1}}],
    }
    assert converted[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "boom", "is_error": True}
        ],
    }


class FakeMessages:
    def __init__(self, response: AnthropicMessage) -> None:
        self.response = response
        self.kwargs: dict = {}

    async def create(self, **kwargs) -> AnthropicMessage:
        self.kwargs = kwargs
        return self.response


class FakeClient:
    """Stands in for anthropic.AsyncAnthropic and answers with a real Message."""

    def __init__(self, response: AnthropicMessage) -> None:
        self.messages = FakeMessages(response)


async def test_empty_system_and_tools_are_left_out() -> None:
    """The API refuses an empty tool list and treats an empty system prompt as one."""
    client = FakeClient(_response(TextBlock(type="text", text="done")))
    reply = await AnthropicBackend("claude-test", client=client).complete(
        "", [Message("user", "hi")], []
    )
    assert reply == Message("assistant", "done")
    assert "system" not in client.messages.kwargs
    assert "tools" not in client.messages.kwargs
    assert client.messages.kwargs["max_tokens"] > 0
