from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import write_json


def load_omnigent_chat_history(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return omnigent_payload_to_chat_history(payload)


def write_omnigent_chat_history(payload: dict[str, Any] | list[dict[str, Any]], out_path: Path) -> None:
    if isinstance(payload, dict) and payload.get("source") == "omnigent_session_events" and "messages" in payload:
        write_json(out_path, payload)
        return
    write_json(out_path, omnigent_payload_to_chat_history(payload))


def omnigent_payload_to_chat_history(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    events = _extract_events(payload)
    session_id = _session_id(payload)
    messages: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        message = _event_to_message(event, session_id=session_id, index=index)
        if message is not None:
            messages.append(message)
    return {
        "conversation_id": session_id,
        "source": "omnigent_session_events",
        "objective": payload.get("objective") if isinstance(payload, dict) else None,
        "created_at": payload.get("created_at") if isinstance(payload, dict) else None,
        "messages": messages,
    }


def _extract_events(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [event for event in payload if isinstance(event, dict)]
    for key in ["events", "items", "messages", "conversation_items", "data"]:
        value = payload.get(key)
        if isinstance(value, list):
            return [event for event in value if isinstance(event, dict)]
    return []


def _session_id(payload: dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(payload, dict):
        for key in ["session_id", "conversation_id", "id"]:
            value = payload.get(key)
            if value:
                return str(value)
    return "omnigent_session"


def _event_to_message(event: dict[str, Any], *, session_id: str, index: int) -> dict[str, Any] | None:
    event_type = str(event.get("type") or event.get("object") or "event")
    content = _content_blocks(event, event_type)
    if not content:
        return None

    metadata = {
        "source": "omnigent",
        "omnigent_event_type": event_type,
        "session_id": session_id,
    }
    for key in ["sequence_number", "response_id", "call_id", "tool_call_id", "name"]:
        if event.get(key) is not None:
            metadata[key] = event[key]

    message: dict[str, Any] = {
        "id": str(event.get("id") or event.get("item_id") or f"turn_{index:03d}"),
        "role": _role_for_event(event, event_type),
        "phase": _phase_for_event(event, event_type),
        "timestamp": event.get("timestamp") or event.get("created_at") or event.get("created"),
        "content": content,
        "metadata": metadata,
    }
    if event.get("tool_calls"):
        message["tool_calls"] = event["tool_calls"]
    return message


def _role_for_event(event: dict[str, Any], event_type: str) -> str:
    author = event.get("author")
    author_role = author.get("role") if isinstance(author, dict) else None
    role = event.get("role") or author_role
    if role:
        return str(role)
    lowered = event_type.lower()
    if "tool" in lowered or "function_call_output" in lowered:
        return "tool"
    if lowered == "response.elicitation_request":
        return "system"
    if lowered.startswith("response.") or lowered in {"external_assistant_message", "assistant_message"}:
        return "assistant"
    return "system"


def _phase_for_event(event: dict[str, Any], event_type: str) -> str:
    if event.get("phase"):
        return str(event["phase"])
    lowered = " ".join(
        str(value).lower()
        for value in [event_type, event.get("name"), event.get("tool_name"), event.get("target")]
        if value
    )
    if "elicitation" in lowered or "approval" in lowered:
        return "approval"
    if "instagram" in lowered or "composio" in lowered or "post" in lowered:
        return "posting"
    if "analytics" in lowered or "metric" in lowered:
        return "analytics"
    if "fal" in lowered or "generation" in lowered or "video" in lowered or "image" in lowered:
        return "generation"
    if "gemini" in lowered or "research" in lowered or "analysis" in lowered:
        return "research"
    return "chat"


def _content_blocks(event: dict[str, Any], event_type: str) -> list[dict[str, Any]]:
    raw_content = event.get("content")
    blocks = _normalize_content(raw_content)
    if blocks:
        return blocks

    if event_type == "response.elicitation_request":
        data = event.get("data")
        data_params = data.get("params") if isinstance(data, dict) else {}
        params = event.get("params") or data_params or {}
        return [
            {
                "type": "approval_request",
                "text": str(params.get("message") or ""),
                "policy_name": params.get("policy_name"),
                "phase": params.get("phase"),
                "content_preview": params.get("content_preview"),
            }
        ]

    for key in ["text", "message", "output_text"]:
        if event.get(key):
            return [{"type": "text", "text": str(event[key])}]
    if event.get("delta"):
        return [{"type": "text", "text": str(event["delta"])}]

    response = event.get("response")
    if isinstance(response, dict):
        response_text = response.get("output_text") or response.get("text")
        if response_text:
            return [{"type": "text", "text": str(response_text)}]

    if "output" in event or "result" in event:
        output = event.get("output", event.get("result"))
        return [
            {
                "type": "tool_result",
                "tool_name": event.get("name") or event.get("tool_name"),
                "text": _stringify(output),
                "payload": output if isinstance(output, (dict, list)) else None,
            }
        ]

    return []


def _normalize_content(raw_content: Any) -> list[dict[str, Any]]:
    if raw_content is None:
        return []
    if isinstance(raw_content, str):
        return [{"type": "text", "text": raw_content}]
    if isinstance(raw_content, dict):
        return [_normalize_block(raw_content)]
    if isinstance(raw_content, list):
        blocks = [_normalize_block(block) for block in raw_content if isinstance(block, dict)]
        return [block for block in blocks if block]
    return [{"type": "text", "text": str(raw_content)}]


def _normalize_block(block: dict[str, Any]) -> dict[str, Any]:
    block_type = str(block.get("type") or "text")
    if block_type in {"input_text", "output_text"}:
        return {"type": "text", "text": str(block.get("text") or "")}
    if "text" in block:
        normalized = dict(block)
        normalized["type"] = "text" if block_type == "text" else block_type
        normalized["text"] = str(block["text"])
        return normalized
    return dict(block)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
