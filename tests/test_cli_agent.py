"""The agent command end to end: a real stdio server, a scripted model, the real CLI."""

import json
import sys
from pathlib import Path

import pytest

from mcp_servers_cli import cli
from mcp_servers_cli.llm import Message, ToolCall

SERVER = Path(__file__).parent / "fixtures" / "add_server.py"
TARGET = ["--stdio", f'"{sys.executable}" "{SERVER}"', "--quiet"]


class ScriptedBackend:
    def __init__(self, *replies: Message) -> None:
        self.replies = list(replies)

    async def complete(self, system, messages, tools) -> Message:
        return self.replies.pop(0)


def use_backend(monkeypatch, backend: ScriptedBackend) -> None:
    monkeypatch.setattr(cli, "create_backend", lambda name, model: backend)


def test_agent_prints_each_call_then_the_answer(monkeypatch, capsys) -> None:
    use_backend(
        monkeypatch,
        ScriptedBackend(
            Message("assistant", tool_calls=(ToolCall("c1", "add", {"a": 1, "b": 2}),)),
            Message("assistant", "The sum is 3."),
        ),
    )
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["agent", "1 + 2?", "--model", "scripted", *TARGET])

    output = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert '-> add {"a": 1, "b": 2}' in output
    assert "<- add ok" in output
    assert output.rstrip().endswith("The sum is 3.")


def test_agent_without_an_answer_fails_in_one_line(monkeypatch, capsys) -> None:
    loop = Message("assistant", tool_calls=(ToolCall("c1", "add", {"a": 1, "b": 1}),))
    use_backend(monkeypatch, ScriptedBackend(loop, loop))
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["agent", "loop", "--model", "scripted", "--max-steps", "2", *TARGET])

    assert exit_info.value.code == 1
    assert capsys.readouterr().err.strip() == (
        "error: no final answer after 2 model turns (see --max-steps)"
    )


def test_an_unknown_backend_fails_before_launching_the_server(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["agent", "hi", "--model", "m", "--backend", "gpt", "--stdio", "missing-cmd"])

    assert exit_info.value.code == 1
    assert "Unknown backend 'gpt'" in capsys.readouterr().err


def test_dry_run_shows_the_plan_and_runs_nothing(monkeypatch, capsys, tmp_path) -> None:
    plan = Message("assistant", tool_calls=(ToolCall("c1", "add", {"a": 1, "b": 2}),))
    use_backend(monkeypatch, ScriptedBackend(plan))
    trace = tmp_path / "plan.jsonl"
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["agent", "1 + 2?", "--model", "m", "--dry-run", "--trace", str(trace), *TARGET])

    output = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert "1 call(s) planned, none executed" in output
    assert '-> add {"a": 1, "b": 2}' in output
    assert "<- add" not in output
    events = [json.loads(line)["event"] for line in trace.read_text().splitlines()]
    assert events == ["planned", "end"]


def test_trace_records_each_executed_call(monkeypatch, tmp_path) -> None:
    use_backend(
        monkeypatch,
        ScriptedBackend(
            Message("assistant", tool_calls=(ToolCall("c1", "add", {"a": 2, "b": 3}),)),
            Message("assistant", "5"),
        ),
    )
    trace = tmp_path / "run.jsonl"
    with pytest.raises(SystemExit):
        cli.main(["agent", "2 + 3?", "--model", "m", "--trace", str(trace), *TARGET])

    tool, end = [json.loads(line) for line in trace.read_text().splitlines()]
    assert (tool["tool"], tool["result"], tool["is_error"]) == ("add", "5", False)
    assert (end["steps"], end["answer"]) == (2, "5")
