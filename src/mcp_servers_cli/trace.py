"""A JSON Lines record of an agent run: one object per event, readable with jq or pandas."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from mcp_servers_cli.llm import ToolCall, ToolResult

EXCERPT_CHARS = 500


def excerpt(text: str) -> str:
    return text if len(text) <= EXCERPT_CHARS else f"{text[:EXCERPT_CHARS]}…"


class JsonlTrace:
    """Writes and flushes one line per event, so an interrupted run still leaves its trace."""

    def __init__(self, path: Path) -> None:
        self._file = path.open("w", encoding="utf-8")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self._file.close()

    def _write(self, event: str, **fields: Any) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        self._file.write(json.dumps({"time": now, "event": event, **fields}, ensure_ascii=False))
        self._file.write("\n")
        self._file.flush()

    def tool(self, call: ToolCall, result: ToolResult, elapsed: float) -> None:
        self._write(
            "tool",
            call_id=call.id,
            tool=call.name,
            arguments=call.arguments,
            duration_ms=round(elapsed * 1000, 1),
            is_error=result.is_error,
            result_chars=len(result.content),
            result=excerpt(result.content),
        )

    def planned(self, call: ToolCall) -> None:
        self._write("planned", call_id=call.id, tool=call.name, arguments=call.arguments)

    def end(self, *, steps: int, stopped: bool, answer: str) -> None:
        self._write("end", steps=steps, stopped=stopped, answer=excerpt(answer))


class NullTrace:
    """Same interface, records nothing: the caller never has to test for a missing trace."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def tool(self, call: ToolCall, result: ToolResult, elapsed: float) -> None:
        pass

    def planned(self, call: ToolCall) -> None:
        pass

    def end(self, *, steps: int, stopped: bool, answer: str) -> None:
        pass


Trace = JsonlTrace | NullTrace


def open_trace(path: Path | None) -> Trace:
    return JsonlTrace(path) if path else NullTrace()
