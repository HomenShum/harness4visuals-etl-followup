from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from .extract import extract_signals
from .io import write_json, write_jsonl
from .models import ChatMessage, PipelineResult, PreferenceSignal, PromptRecord, TrainingExample


def run_pipeline(messages: list[ChatMessage]) -> PipelineResult:
    signals = extract_signals(messages)
    taste_profile = build_taste_profile(signals)
    prompts = build_prompt_records(signals)
    training_examples = build_training_examples(messages, signals, prompts)
    manifest = {
        "pipeline": "harness4visuals-etl-followup",
        "version": "0.1.0",
        "input_turns": len(messages),
        "signal_count": len(signals),
        "prompt_count": len(prompts),
        "training_example_count": len(training_examples),
        "run_fingerprint": _fingerprint(messages, signals),
    }
    return PipelineResult(
        signals=signals,
        taste_profile=taste_profile,
        prompts=prompts,
        training_examples=training_examples,
        manifest=manifest,
    )


def build_taste_profile(signals: list[PreferenceSignal]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        grouped[signal.scope].append(
            {
                "id": signal.id,
                "kind": signal.kind,
                "subject": signal.subject,
                "polarity": signal.polarity,
                "confidence": signal.confidence,
                "weight": signal.weight,
                "source_turn_ids": signal.source_turn_ids,
            }
        )
    return {
        "durable": grouped["durable"],
        "campaign": grouped["campaign"],
        "session": grouped["session"],
    }


def build_prompt_records(signals: list[PreferenceSignal]) -> list[PromptRecord]:
    if not signals:
        return []
    positives = [signal.subject for signal in signals if signal.polarity == "positive"]
    negatives = [signal.subject for signal in signals if signal.polarity == "negative"]
    prompt = (
        "Generate a social content concept that reflects the user's durable taste. "
        f"Lean into: {_join_for_prompt(positives)}. "
        f"Avoid: {_join_for_prompt(negatives)}. "
        "Return a concise, model-ready prompt with visual direction, voice, and constraints."
    )
    record_id = _hash_text(prompt)
    return [
        PromptRecord(
            id=f"prompt_{record_id}",
            target="social_generation_prompt",
            prompt=prompt,
            source_signal_ids=[signal.id for signal in signals],
        )
    ]


def build_training_examples(
    messages: list[ChatMessage],
    signals: list[PreferenceSignal],
    prompts: list[PromptRecord],
) -> list[TrainingExample]:
    if not prompts:
        return []
    user_turns = [message.content for message in messages if message.role.lower() == "user"]
    return [
        TrainingExample(
            instruction=(
                "Transform messy agent chat history into a faithful, provenance-backed "
                "social generation prompt for the user's taste profile."
            ),
            input={
                "chat_summary": " ".join(user_turns)[0:1200],
                "taste_signals": [signal.to_dict() for signal in signals],
            },
            output={
                "target": prompts[0].target,
                "prompt": prompts[0].prompt,
            },
            metadata={
                "format": "slm_jsonl",
                "source": "chat_history",
                "source_turn_ids": sorted({turn_id for signal in signals for turn_id in signal.source_turn_ids}),
                "source_signal_ids": [signal.id for signal in signals],
            },
        )
    ]


def write_result(result: PipelineResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "signals.jsonl", [signal.to_dict() for signal in result.signals])
    write_json(out_dir / "taste_profile.json", result.taste_profile)
    write_jsonl(out_dir / "prompts.jsonl", [prompt.to_dict() for prompt in result.prompts])
    write_jsonl(out_dir / "training.jsonl", [example.to_dict() for example in result.training_examples])
    write_json(out_dir / "manifest.json", result.manifest)


def _join_for_prompt(values: list[str]) -> str:
    return ", ".join(values) if values else "no explicit signals"


def _fingerprint(messages: list[ChatMessage], signals: list[PreferenceSignal]) -> str:
    raw = "|".join([message.id + message.content for message in messages])
    raw += "|" + "|".join(signal.id for signal in signals)
    return _hash_text(raw)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
