"""The tool loop against an in-memory FastMCP server and a scripted model: no LLM, no network."""

import pytest
from fastmcp import Client, FastMCP

from mcp_servers_cli.agent import MAX_RESULT_CHARS, result_text, run_agent, sanitize_args
from mcp_servers_cli.llm import Message, ToolCall


class ScriptedBackend:
    """Replays assistant turns in order and records every request it receives."""

    def __init__(self, *replies: Message) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[str, list[Message], list]] = []

    async def complete(self, system, messages, tools) -> Message:
        self.requests.append((system, list(messages), list(tools)))
        return self.replies.pop(0)


def ask(*calls: ToolCall) -> Message:
    return Message("assistant", tool_calls=calls)


def answer(text: str) -> Message:
    return Message("assistant", text)


@pytest.fixture
def server() -> FastMCP:
    mcp = FastMCP("Test")

    @mcp.tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    @mcp.tool
    def fail() -> str:
        """Always fails."""
        raise ValueError("disk full")

    return mcp


async def test_a_text_reply_ends_the_run_at_once(server) -> None:
    backend = ScriptedBackend(answer("nothing to do"))
    async with Client(server) as client:
        run = await run_agent(client, backend, "hello", system="be brief")

    assert (run.answer, run.steps, run.stopped) == ("nothing to do", 1, False)
    system, _, tools = backend.requests[0]
    assert system == "be brief"
    assert sorted(tool.name for tool in tools) == ["add", "fail"]


async def test_results_are_fed_back_to_the_model(server) -> None:
    backend = ScriptedBackend(ask(ToolCall("c1", "add", {"a": 1, "b": 2})), answer("3"))
    async with Client(server) as client:
        run = await run_agent(client, backend, "1 + 2?")

    assert (run.answer, run.steps) == ("3", 2)
    tool_turn = backend.requests[1][1][-1]
    assert tool_turn.role == "tool"
    assert (tool_turn.tool_results[0].call_id, tool_turn.tool_results[0].content) == ("c1", "3")
    assert not tool_turn.tool_results[0].is_error


async def test_invented_arguments_are_dropped(server) -> None:
    backend = ScriptedBackend(ask(ToolCall("c1", "add", {"a": 1, "b": 2, "c": 9})), answer("3"))
    async with Client(server) as client:
        run = await run_agent(client, backend, "1 + 2?")

    assert not run.messages[2].tool_results[0].is_error


async def test_a_failing_tool_is_reported_to_the_model(server) -> None:
    backend = ScriptedBackend(ask(ToolCall("c1", "fail", {})), answer("could not"))
    async with Client(server) as client:
        run = await run_agent(client, backend, "try")

    result = run.messages[2].tool_results[0]
    assert result.is_error
    assert "disk full" in result.content


async def test_an_unknown_tool_is_reported_with_the_available_ones(server) -> None:
    backend = ScriptedBackend(ask(ToolCall("c1", "multiply", {})), answer("sorry"))
    async with Client(server) as client:
        run = await run_agent(client, backend, "2 * 3?")

    result = run.messages[2].tool_results[0]
    assert result.is_error
    assert "available: add, fail" in result.content


async def test_the_step_budget_stops_a_model_that_never_answers(server) -> None:
    loop = ask(ToolCall("c1", "add", {"a": 1, "b": 1}))
    backend = ScriptedBackend(loop, loop, loop)
    async with Client(server) as client:
        run = await run_agent(client, backend, "keep going", max_steps=2)

    assert (run.stopped, run.steps, len(backend.requests)) == (True, 2, 2)


async def test_hooks_see_each_call_and_its_duration(server) -> None:
    seen = []
    backend = ScriptedBackend(ask(ToolCall("c1", "add", {"a": 2, "b": 2})), answer("4"))
    async with Client(server) as client:
        await run_agent(
            client,
            backend,
            "2 + 2?",
            on_tool_call=lambda call: seen.append(("call", call.name)),
            on_tool_result=lambda call, result, elapsed: seen.append(("result", elapsed >= 0)),
        )

    assert seen == [("call", "add"), ("result", True)]


def test_a_schema_without_properties_keeps_every_argument() -> None:
    assert sanitize_args({"x": 1}, {"type": "object"}) == {"x": 1}


def test_long_results_are_truncated() -> None:
    class Result:
        content = []
        structured_content = {"text": "x" * (MAX_RESULT_CHARS + 10)}

    text = result_text(Result())
    assert len(text) < MAX_RESULT_CHARS + 100
    assert "[truncated:" in text
