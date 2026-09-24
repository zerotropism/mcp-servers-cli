"""Ollama translation, checked against the SDK's own types rather than hand-written dicts."""

import ollama

from mcp_servers_cli.backends.ollama import (
    OllamaBackend,
    from_ollama_message,
    normalize_args,
    to_ollama_messages,
    to_ollama_tool,
)
from mcp_servers_cli.llm import Message, ToolCall, ToolResult, ToolSpec

TOOL = ToolSpec("add", "Add a number", {"type": "object", "properties": {"a": {"type": "integer"}}})


def _call(name: str, arguments: dict) -> ollama.Message.ToolCall:
    return ollama.Message.ToolCall(
        function=ollama.Message.ToolCall.Function(name=name, arguments=arguments)
    )


def test_schema_leaked_into_a_value_is_unwrapped() -> None:
    assert normalize_args({"a": {"type": "integer", "value": 1}}) == {"a": 1}


def test_a_genuine_nested_object_is_kept() -> None:
    nested = {"window": {"value": 60, "unit": "s"}}
    assert normalize_args(nested) == nested


def test_tool_is_declared_as_a_function() -> None:
    declared = to_ollama_tool(TOOL)
    assert declared["type"] == "function"
    assert declared["function"]["parameters"] == TOOL.input_schema


def test_calls_without_ids_are_numbered_and_normalized() -> None:
    raw = ollama.Message(
        role="assistant",
        tool_calls=[_call("add", {"a": {"type": "integer", "value": 1}}), _call("add", {"a": 2})],
    )
    calls = from_ollama_message(raw).tool_calls
    assert [call.id for call in calls] == ["call_0", "call_1"]
    assert [call.arguments for call in calls] == [{"a": 1}, {"a": 2}]


def test_each_result_becomes_one_tool_message_in_call_order() -> None:
    history = [
        Message("user", "add one"),
        Message("assistant", tool_calls=(ToolCall("call_0", "add", {"a": 1}),)),
        Message(
            "tool",
            tool_results=(
                ToolResult("call_0", "add", "1"),
                ToolResult("call_1", "add", "boom", is_error=True),
            ),
        ),
    ]
    converted = to_ollama_messages("be brief", history)
    assert converted[0] == {"role": "system", "content": "be brief"}
    assert converted[2]["tool_calls"] == [{"function": {"name": "add", "arguments": {"a": 1}}}]
    assert converted[3:] == [
        {"role": "tool", "tool_name": "add", "content": "1"},
        {"role": "tool", "tool_name": "add", "content": "error: boom"},
    ]


class FakeClient:
    """Stands in for ollama.AsyncClient and answers with a real ChatResponse."""

    def __init__(self, reply: ollama.Message) -> None:
        self.reply = reply
        self.kwargs: dict = {}

    async def chat(self, **kwargs) -> ollama.ChatResponse:
        self.kwargs = kwargs
        return ollama.ChatResponse(model=kwargs["model"], message=self.reply)


async def test_complete_sends_the_model_the_messages_and_the_tools() -> None:
    client = FakeClient(ollama.Message(role="assistant", content="done"))
    reply = await OllamaBackend("qwen3.5:4b", client=client).complete(
        "", [Message("user", "hi")], [TOOL]
    )
    assert reply == Message("assistant", "done")
    assert client.kwargs["model"] == "qwen3.5:4b"
    assert client.kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert client.kwargs["tools"][0]["function"]["name"] == "add"
