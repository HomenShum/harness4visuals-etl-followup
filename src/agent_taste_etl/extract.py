from __future__ import annotations

import hashlib
import re
from collections import OrderedDict

from .models import ChatMessage, PreferenceSignal

_NEGATIVE_PATTERNS = [
    re.compile(r"\bavoid\s+(.+)", re.IGNORECASE),
    re.compile(r"\bdo not use\s+(.+)", re.IGNORECASE),
    re.compile(r"\bdon't use\s+(.+)", re.IGNORECASE),
    re.compile(r"\bless\s+(.+?)(?=\s+and\s+(?:a|an|the)\s+|$|[,.])", re.IGNORECASE),
    re.compile(r"\bremove\s+(.+)", re.IGNORECASE),
    re.compile(r"\bdislike\s+(.+)", re.IGNORECASE),
]

_POSITIVE_PATTERNS = [
    re.compile(r"\bmy durable taste is still\s+(.+)", re.IGNORECASE),
    re.compile(r"\bi like\s+(.+)", re.IGNORECASE),
    re.compile(r"\bi love\s+(.+)", re.IGNORECASE),
    re.compile(r"\bprefer\s+(.+)", re.IGNORECASE),
    re.compile(r"\bkeep\s+(.+)", re.IGNORECASE),
    re.compile(r"\bmore\s+([^,.]+)", re.IGNORECASE),
    re.compile(r"\bcan be more\s+(.+)", re.IGNORECASE),
    re.compile(r"\bfeel\s+(.+)", re.IGNORECASE),
]


def extract_signals(messages: list[ChatMessage]) -> list[PreferenceSignal]:
    signals: OrderedDict[str, PreferenceSignal] = OrderedDict()
    for message in messages:
        if message.role.lower() != "user":
            continue
        for sentence in _split_sentences(message.content):
            for subject in _extract_subjects(sentence, polarity="negative"):
                signal = _build_signal(message, sentence, subject, "negative")
                signals.setdefault(_dedupe_key(signal), signal)
            for subject in _extract_subjects(sentence, polarity="positive"):
                signal = _build_signal(message, sentence, subject, "positive")
                signals.setdefault(_dedupe_key(signal), signal)
    return list(signals.values())


def _split_sentences(content: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", content.strip())
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def _extract_subjects(sentence: str, polarity: str) -> list[str]:
    patterns = _NEGATIVE_PATTERNS if polarity == "negative" else _POSITIVE_PATTERNS
    subjects: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(sentence):
            phrase = _clean_phrase(match.group(1))
            subjects.extend(_split_phrase(phrase))
    return [_normalize_subject(subject) for subject in subjects if _normalize_subject(subject)]


def _clean_phrase(phrase: str) -> str:
    phrase = re.split(r"\bbut\b|\bonly for\b|\bwhile\b", phrase, maxsplit=1, flags=re.IGNORECASE)[0]
    phrase = re.sub(r"^(the content to|it to|it|that|them|use)\s+", "", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\s+", " ", phrase)
    return phrase.strip(" .;:")


def _split_phrase(phrase: str) -> list[str]:
    phrase = phrase.replace(" and ", ", ")
    parts = [part.strip(" ,") for part in phrase.split(",")]
    return [part for part in parts if part and len(part) > 2]


def _normalize_subject(subject: str) -> str:
    subject = subject.lower().strip()
    subject = re.sub(r"^(more|less|a|an|the)\s+", "", subject)
    subject = re.sub(r"\s+", " ", subject)
    if subject.startswith("captions "):
        suffix = subject.removeprefix("captions ").strip()
        if suffix:
            return f"{suffix} captions"
    return subject.strip(" .;:")


def _build_signal(
    message: ChatMessage,
    evidence: str,
    subject: str,
    polarity: str,
) -> PreferenceSignal:
    scope = _infer_scope(evidence, polarity)
    kind = _infer_kind(subject)
    confidence = 0.82 if scope == "durable" else 0.74
    weight = 0.9 if scope == "durable" else 0.65
    signal_id = _stable_id(kind, subject, polarity, scope, [message.id])
    return PreferenceSignal(
        id=signal_id,
        kind=kind,
        subject=subject,
        polarity=polarity,  # type: ignore[arg-type]
        scope=scope,
        confidence=confidence,
        weight=weight,
        evidence=evidence,
        source_turn_ids=[message.id],
    )


def _infer_scope(evidence: str, polarity: str) -> str:
    lowered = evidence.lower()
    if any(token in lowered for token in ["campaign", "launch week", "only for"]):
        return "campaign"
    if any(token in lowered for token in ["my brand", "my taste", "durable taste", "i like", "i love", "prefer", "i want"]):
        return "durable"
    if any(token in lowered for token in ["this version", "second version", "more ", "less "]):
        return "session"
    return "durable" if polarity == "negative" else "session"


def _infer_kind(subject: str) -> str:
    lowered = subject.lower()
    if any(token in lowered for token in ["caption", "language", "voice", "punchy", "concise", "witty"]):
        return "voice"
    if any(token in lowered for token in ["shot", "screen", "footage", "cut", "video"]):
        return "visual"
    if any(token in lowered for token in ["testimonial", "claim", "proof"]):
        return "trust"
    return "aesthetic"


def _stable_id(kind: str, subject: str, polarity: str, scope: str, source_ids: list[str]) -> str:
    raw = "|".join([kind, subject, polarity, scope, ",".join(source_ids)])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"sig_{digest}"


def _dedupe_key(signal: PreferenceSignal) -> str:
    return "|".join([signal.kind, signal.subject, signal.polarity, signal.scope])
