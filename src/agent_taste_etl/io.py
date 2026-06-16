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
        content, content_blocks = _normalize_content(item.get("content", ""))
        messages.append(
            ChatMessage(
                id=str(item.get("id") or f"turn_{index:03d}"),
                role=str(item["role"]),
                content=content,
                timestamp=item.get("timestamp"),
                content_blocks=content_blocks,
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return messages


def _normalize_content(raw_content: Any) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(raw_content, str):
        return raw_content, [{"type": "text", "text": raw_content}]
    if isinstance(raw_content, list):
        blocks = [block for block in raw_content if isinstance(block, dict)]
        text_parts = [_block_to_text(block) for block in blocks]
        return " ".join(part for part in text_parts if part).strip(), blocks
    return str(raw_content), [{"type": "text", "text": str(raw_content)}]


def _block_to_text(block: dict[str, Any]) -> str:
    if "text" in block:
        return str(block["text"])
    if block.get("type") in {"image_reference", "video_reference", "audio_reference", "generated_asset"}:
        label = block.get("label") or block.get("asset_id") or block.get("uri") or block.get("url")
        notes = block.get("notes")
        return " ".join(str(value) for value in [label, notes] if value)
    if block.get("type") == "selection":
        selected = ", ".join(str(item) for item in block.get("selected_asset_ids", []))
        reason = block.get("reason", "")
        return f"selected {selected} {reason}".strip()
    return ""


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
