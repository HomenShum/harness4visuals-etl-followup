from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import read_jsonl

REQUIRED_SIGNAL_FIELDS = {
    "id",
    "kind",
    "subject",
    "polarity",
    "scope",
    "confidence",
    "weight",
    "evidence",
    "source_turn_ids",
}


@dataclass(frozen=True)
class EvaluationResult:
    metrics: dict[str, float]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"metrics": self.metrics, "errors": self.errors}


def evaluate_files(predictions_path: Path, golden_path: Path) -> EvaluationResult:
    predictions = read_jsonl(predictions_path)
    golden = read_jsonl(golden_path)
    return evaluate_rows(predictions, golden)


def evaluate_rows(predictions: list[dict[str, Any]], golden: list[dict[str, Any]]) -> EvaluationResult:
    errors = _validate_signals(predictions)
    matches = _match_predictions(predictions, golden)
    true_positive = len(matches)
    false_positive = max(len(predictions) - true_positive, 0)
    false_negative = max(len(golden) - true_positive, 0)
    precision = _divide(true_positive, true_positive + false_positive)
    recall = _divide(true_positive, true_positive + false_negative)
    f1 = _divide(2 * precision * recall, precision + recall)
    schema_validity_rate = _divide(len(predictions) - len(errors), len(predictions))
    provenance_rate = _divide(
        sum(1 for row in predictions if row.get("source_turn_ids") and row.get("evidence")),
        len(predictions),
    )
    hallucinated_preference_rate = _divide(false_positive, len(predictions))
    return EvaluationResult(
        metrics={
            "schema_validity_rate": round(schema_validity_rate, 4),
            "provenance_rate": round(provenance_rate, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "hallucinated_preference_rate": round(hallucinated_preference_rate, 4),
            "true_positive": float(true_positive),
            "false_positive": float(false_positive),
            "false_negative": float(false_negative),
        },
        errors=errors,
    )


def assert_thresholds(result: EvaluationResult, min_f1: float, max_hallucination_rate: float) -> None:
    metrics = result.metrics
    failures: list[str] = []
    if metrics["schema_validity_rate"] < 1.0:
        failures.append("schema_validity_rate must be 1.0")
    if metrics["provenance_rate"] < 1.0:
        failures.append("provenance_rate must be 1.0")
    if metrics["f1"] < min_f1:
        failures.append(f"f1 must be >= {min_f1}")
    if metrics["hallucinated_preference_rate"] > max_hallucination_rate:
        failures.append(f"hallucinated_preference_rate must be <= {max_hallucination_rate}")
    if failures:
        raise AssertionError(json.dumps({"failures": failures, "result": result.to_dict()}, indent=2))


def _validate_signals(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        line = row.get("_line_number", "?")
        missing = REQUIRED_SIGNAL_FIELDS - set(row)
        if missing:
            errors.append(f"line {line}: missing fields {sorted(missing)}")
        if row.get("polarity") not in {"positive", "negative"}:
            errors.append(f"line {line}: invalid polarity")
        if row.get("scope") not in {"durable", "campaign", "session"}:
            errors.append(f"line {line}: invalid scope")
        if not isinstance(row.get("source_turn_ids"), list) or not row.get("source_turn_ids"):
            errors.append(f"line {line}: source_turn_ids must be a non-empty list")
    return errors


def _match_predictions(
    predictions: list[dict[str, Any]],
    golden: list[dict[str, Any]],
) -> list[tuple[int, int]]:
    matched_golden: set[int] = set()
    matches: list[tuple[int, int]] = []
    for prediction_index, prediction in enumerate(predictions):
        best_index = None
        best_score = 0.0
        for golden_index, golden_row in enumerate(golden):
            if golden_index in matched_golden:
                continue
            score = _signal_similarity(prediction, golden_row)
            if score > best_score:
                best_score = score
                best_index = golden_index
        if best_index is not None and best_score >= 0.72:
            matched_golden.add(best_index)
            matches.append((prediction_index, best_index))
    return matches


def _signal_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    if left.get("polarity") != right.get("polarity"):
        return 0.0
    scope_score = 1.0 if left.get("scope") == right.get("scope") else 0.6
    kind_score = 1.0 if left.get("kind") == right.get("kind") else 0.7
    subject_score = _token_jaccard(str(left.get("subject", "")), str(right.get("subject", "")))
    return (0.25 * scope_score) + (0.25 * kind_score) + (0.5 * subject_score)


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[a-z0-9-]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9-]+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0

