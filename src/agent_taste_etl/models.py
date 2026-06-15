from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Polarity = Literal["positive", "negative"]
Scope = Literal["durable", "campaign", "session"]


@dataclass(frozen=True)
class ChatMessage:
    id: str
    role: str
    content: str
    timestamp: str | None = None


@dataclass(frozen=True)
class PreferenceSignal:
    id: str
    kind: str
    subject: str
    polarity: Polarity
    scope: Scope
    confidence: float
    weight: float
    evidence: str
    source_turn_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromptRecord:
    id: str
    target: str
    prompt: str
    source_signal_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrainingExample:
    instruction: str
    input: dict[str, Any]
    output: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineResult:
    signals: list[PreferenceSignal]
    taste_profile: dict[str, Any]
    prompts: list[PromptRecord]
    training_examples: list[TrainingExample]
    manifest: dict[str, Any]

