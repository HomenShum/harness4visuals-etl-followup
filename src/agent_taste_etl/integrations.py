from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from .io import write_json, write_jsonl
from .models import PipelineResult, TrainingExample

DEFAULT_PIONEER_BASE_MODEL = "Qwen/Qwen3-8B"


def build_clickhouse_rows(
    result: PipelineResult,
    *,
    conversation_id: str,
    user_id: str,
    dataset_name: str,
) -> dict[str, list[dict[str, Any]]]:
    run_id = f"run_{result.manifest['run_fingerprint']}"
    run_rows = [
        {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "pipeline": result.manifest["pipeline"],
            "version": result.manifest["version"],
            "input_turns": result.manifest["input_turns"],
            "signal_count": result.manifest["signal_count"],
            "prompt_count": result.manifest["prompt_count"],
            "training_example_count": result.manifest["training_example_count"],
            "run_fingerprint": result.manifest["run_fingerprint"],
            "manifest_json": _compact_json(result.manifest),
        }
    ]
    signal_rows = [
        {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "signal_id": signal.id,
            "kind": signal.kind,
            "subject": signal.subject,
            "polarity": signal.polarity,
            "scope": signal.scope,
            "confidence": signal.confidence,
            "weight": signal.weight,
            "evidence": signal.evidence,
            "source_turn_ids": signal.source_turn_ids,
            "payload_json": _compact_json(signal.to_dict()),
        }
        for signal in result.signals
    ]
    prompt_rows = [
        {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "prompt_id": prompt.id,
            "target": prompt.target,
            "prompt": prompt.prompt,
            "source_signal_ids": prompt.source_signal_ids,
            "payload_json": _compact_json(prompt.to_dict()),
        }
        for prompt in result.prompts
    ]
    training_rows = [
        {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "dataset_name": dataset_name,
            "example_id": _training_example_id(example),
            "format": example.metadata.get("format", "slm_jsonl"),
            "instruction": example.instruction,
            "input_json": _compact_json(example.input),
            "output_json": _compact_json(example.output),
            "source_turn_ids": example.metadata.get("source_turn_ids", []),
            "source_signal_ids": example.metadata.get("source_signal_ids", []),
            "payload_json": _compact_json(example.to_dict()),
        }
        for example in result.training_examples
    ]
    return {
        "runs": run_rows,
        "preference_signals": signal_rows,
        "prompt_records": prompt_rows,
        "training_examples": training_rows,
    }


def write_clickhouse_export(rows: dict[str, list[dict[str, Any]]], out_dir: Path) -> None:
    write_jsonl(out_dir / "runs.jsonl", rows["runs"])
    write_jsonl(out_dir / "preference_signals.jsonl", rows["preference_signals"])
    write_jsonl(out_dir / "prompt_records.jsonl", rows["prompt_records"])
    write_jsonl(out_dir / "training_examples.jsonl", rows["training_examples"])


def build_pioneer_decoder_sft_rows(
    result: PipelineResult,
    *,
    system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    instruction = system_prompt or (
        "You transform messy creative-agent chat history into faithful, "
        "provenance-backed social generation prompts. Preserve durable taste, "
        "separate campaign-only constraints, and avoid inventing preferences."
    )
    rows: list[dict[str, Any]] = []
    for example in result.training_examples:
        rows.append(
            {
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": _pioneer_user_content(example)},
                    {"role": "assistant", "content": _compact_json(example.output)},
                ]
            }
        )
    return rows


def build_pioneer_manifest(
    result: PipelineResult,
    *,
    dataset_name: str,
    base_model: str = DEFAULT_PIONEER_BASE_MODEL,
) -> dict[str, Any]:
    return {
        "provider": "pioneer",
        "dataset_name": dataset_name,
        "dataset_type": "decoder",
        "format": "jsonl",
        "recommended_base_model": base_model,
        "training_algorithm": "sft",
        "training_type": "lora",
        "source_run_fingerprint": result.manifest["run_fingerprint"],
        "source_signal_count": result.manifest["signal_count"],
        "source_training_example_count": result.manifest["training_example_count"],
        "provenance_note": (
            "Upload decoder_sft.jsonl to Pioneer as a decoder dataset. Keep this "
            "manifest next to the uploaded dataset because Pioneer chat SFT rows "
            "should stay provider-clean and contain only messages."
        ),
    }


def build_pioneer_upload_request(dataset_name: str) -> dict[str, Any]:
    return {
        "dataset_name": dataset_name,
        "dataset_type": "decoder",
        "format": "jsonl",
    }


def build_pioneer_training_job_request(
    *,
    dataset_name: str,
    model_name: str,
    base_model: str = DEFAULT_PIONEER_BASE_MODEL,
) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "base_model": base_model,
        "datasets": [{"name": dataset_name}],
        "training_type": "lora",
        "training_algorithm": "sft",
        "nr_epochs": 3,
        "learning_rate": 5e-5,
        "batch_size": 4,
    }


def write_pioneer_export(
    result: PipelineResult,
    out_dir: Path,
    *,
    dataset_name: str,
    model_name: str,
    base_model: str = DEFAULT_PIONEER_BASE_MODEL,
) -> None:
    rows = build_pioneer_decoder_sft_rows(result)
    write_jsonl(out_dir / "decoder_sft.jsonl", rows)
    write_json(
        out_dir / "dataset_manifest.json",
        build_pioneer_manifest(result, dataset_name=dataset_name, base_model=base_model),
    )
    write_json(out_dir / "dataset_upload_request.json", build_pioneer_upload_request(dataset_name))
    write_json(
        out_dir / "training_job_request.json",
        build_pioneer_training_job_request(
            dataset_name=dataset_name,
            model_name=model_name,
            base_model=base_model,
        ),
    )


def _pioneer_user_content(example: TrainingExample) -> str:
    return _pretty_json(
        {
            "instruction": example.instruction,
            "input": example.input,
            "metadata": {
                "source_turn_ids": example.metadata.get("source_turn_ids", []),
                "source_signal_ids": example.metadata.get("source_signal_ids", []),
            },
        }
    )


def _training_example_id(example: TrainingExample) -> str:
    return f"train_{_hash_text(_compact_json(example.to_dict()))}"


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _pretty_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
