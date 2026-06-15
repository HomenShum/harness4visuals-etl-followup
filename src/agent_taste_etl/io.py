from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import ChatMessage


def load_chat_history(path: Path) -> list[ChatMessage]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_messages = payload["messages"] if isinstance(payload, dict) else payload
    messages: list[ChatMessage] = []
    for index, item in enumerate(raw_messages, start=1):
        messages.append(
            ChatMessage(
                id=str(item.get("id") or f"turn_{index:03d}"),
                role=str(item["role"]),
                content=str(item["content"]),
                timestamp=item.get("timestamp"),
            )
        )
    return messages


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            row = json.loads(line)
            row["_line_number"] = line_number
            rows.append(row)
    return rows

