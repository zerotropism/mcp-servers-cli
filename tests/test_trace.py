"""The JSONL trace: one parseable object per event, excerpts bounded, nothing when disabled."""

import json

from mcp_servers_cli.llm import ToolCall, ToolResult
from mcp_servers_cli.trace import EXCERPT_CHARS, NullTrace, open_trace


def read_lines(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_each_event_is_one_json_line(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    call = ToolCall("c1", "add", {"a": 1, "b": 2})
    with open_trace(path) as trace:
        trace.tool(call, ToolResult("c1", "add", "3"), 0.0123)
        trace.end(steps=2, stopped=False, answer="3")

    tool, end = read_lines(path)
    assert (tool["event"], tool["tool"], tool["arguments"]) == ("tool", "add", {"a": 1, "b": 2})
    assert (tool["duration_ms"], tool["is_error"], tool["result"]) == (12.3, False, "3")
    assert tool["time"].endswith("+00:00")
    assert (end["event"], end["steps"], end["stopped"]) == ("end", 2, False)


def test_long_results_are_cut_but_their_size_is_kept(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    content = "x" * (EXCERPT_CHARS * 3)
    with open_trace(path) as trace:
        trace.tool(ToolCall("c1", "dump", {}), ToolResult("c1", "dump", content), 0.0)

    (tool,) = read_lines(path)
    assert tool["result_chars"] == EXCERPT_CHARS * 3
    assert len(tool["result"]) == EXCERPT_CHARS + 1


def test_no_path_means_no_file(tmp_path) -> None:
    with open_trace(None) as trace:
        trace.planned(ToolCall("c1", "add", {}))
    assert isinstance(trace, NullTrace)
    assert list(tmp_path.iterdir()) == []
