# Harness4Visuals ETL Follow-Up

This repo is a focused follow-up to the original `Harness4Visuals` prototype. It isolates the highest-leverage step in the harnessed agent workflow:

> Can an agent harness reliably transform messy chat history into faithful, provenance-backed taste memory and SLM training JSONL?

The goal is not to demo another provider call. The goal is to make the learning layer testable. If this step works, future remixing, prompting, generation, posting, and analytics can improve over time. If this step is wrong, the agent learns noisy or invented preferences.

## What It Ships

- A deterministic ETL pipeline for chat history.
- Taste and brand preference extraction with source-turn provenance.
- Prompt records shaped for generation models.
- JSONL records suitable for downstream small language model fine-tuning.
- An evaluator that scores schema validity, provenance, precision, recall, F1, and hallucinated preference rate.
- A `verify` command that runs the full test loop against golden data.
- GitHub Actions CI that runs tests plus the verification loop.

## Quick Start

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m agent_taste_etl.cli verify --out out/verify
```

Run the ETL pipeline directly:

```bash
python -m agent_taste_etl.cli run \
  --input examples/chat_history.json \
  --out out/sample
```

Evaluate an output against the golden fixture:

```bash
python -m agent_taste_etl.cli evaluate \
  --predictions out/sample/signals.jsonl \
  --golden examples/golden_signals.jsonl
```

## Harness Contract

The ETL step must produce records that are:

- **Faithful**: extracted from the chat, not inferred from nowhere.
- **Provenanced**: every preference points back to source turns and evidence.
- **Scoped**: durable brand taste is separated from campaign-only or session-only instructions.
- **Negative-aware**: dislikes and avoidances are first-class signals.
- **Model-ready**: training records are valid JSONL with stable metadata.
- **Replayable**: the same input produces the same output.

## Output Files

`run` writes:

- `signals.jsonl`: normalized preference records.
- `taste_profile.json`: grouped durable, campaign, and session preferences.
- `prompts.jsonl`: generation prompt records.
- `training.jsonl`: SLM fine-tuning examples.
- `manifest.json`: deterministic run metadata.

## Step Output Shapes

The harness is intentionally explicit about every intermediate shape. Each snippet below is shortened for readability, but the field names are the contract.

### 0. Chat History Input

Input is a JSON object with ordered chat messages. This is the replay source for the whole pipeline.

```json
{
  "messages": [
    {
      "id": "turn_001",
      "role": "user",
      "timestamp": "2026-06-15T09:00:00-07:00",
      "content": "I want the content to feel energetic, polished, and creator-led. Avoid purple gradients and generic stock footage."
    }
  ]
}
```

### 1. Normalized Chat Messages

The loader normalizes every message into the internal message shape. Missing IDs are filled as deterministic `turn_001`, `turn_002`, etc.

```json
{
  "id": "turn_001",
  "role": "user",
  "content": "I want the content to feel energetic, polished, and creator-led...",
  "timestamp": "2026-06-15T09:00:00-07:00"
}
```

### 2. Preference Signals

`signals.jsonl` contains one normalized preference per line. These records are the main memory artifact.

```json
{
  "id": "sig_0b9c8c5d8f42",
  "kind": "aesthetic",
  "subject": "purple gradients",
  "polarity": "negative",
  "scope": "durable",
  "confidence": 0.82,
  "weight": 0.9,
  "evidence": "Avoid purple gradients and generic stock footage.",
  "source_turn_ids": ["turn_001"]
}
```

Field meaning:

- `kind`: preference family, such as `aesthetic`, `voice`, `visual`, or `trust`.
- `subject`: the extracted taste object.
- `polarity`: `positive` or `negative`.
- `scope`: `durable`, `campaign`, or `session`.
- `confidence`: extraction confidence.
- `weight`: downstream influence strength.
- `evidence`: source text used to justify the signal.
- `source_turn_ids`: provenance back to the chat.

### 3. Taste Profile

`taste_profile.json` groups signals by memory scope for agent retrieval and UI display.

```json
{
  "durable": [
    {
      "id": "sig_0b9c8c5d8f42",
      "kind": "aesthetic",
      "subject": "purple gradients",
      "polarity": "negative",
      "confidence": 0.82,
      "weight": 0.9,
      "source_turn_ids": ["turn_001"]
    }
  ],
  "campaign": [],
  "session": []
}
```

### 4. Generation Prompt Records

`prompts.jsonl` turns preference memory into a model-targeted prompt record.

```json
{
  "id": "prompt_8be44716f3d0",
  "target": "social_generation_prompt",
  "prompt": "Generate a social content concept that reflects the user's durable taste. Lean into: energetic, polished, creator-led. Avoid: purple gradients, generic stock footage. Return a concise, model-ready prompt with visual direction, voice, and constraints.",
  "source_signal_ids": ["sig_123", "sig_456"]
}
```

### 5. SLM Training JSONL

`training.jsonl` is the natural fine-tuning shape for a small language model that learns this transformation.

```json
{
  "instruction": "Transform messy agent chat history into a faithful, provenance-backed social generation prompt for the user's taste profile.",
  "input": {
    "chat_summary": "I want the content to feel energetic, polished, and creator-led...",
    "taste_signals": [
      {
        "id": "sig_0b9c8c5d8f42",
        "kind": "aesthetic",
        "subject": "purple gradients",
        "polarity": "negative",
        "scope": "durable",
        "confidence": 0.82,
        "weight": 0.9,
        "evidence": "Avoid purple gradients and generic stock footage.",
        "source_turn_ids": ["turn_001"]
      }
    ]
  },
  "output": {
    "target": "social_generation_prompt",
    "prompt": "Generate a social content concept..."
  },
  "metadata": {
    "format": "slm_jsonl",
    "source": "chat_history",
    "source_turn_ids": ["turn_001"],
    "source_signal_ids": ["sig_0b9c8c5d8f42"]
  }
}
```

### 6. Run Manifest

`manifest.json` makes each run reproducible and easy to compare in CI.

```json
{
  "pipeline": "harness4visuals-etl-followup",
  "version": "0.1.0",
  "input_turns": 6,
  "signal_count": 15,
  "prompt_count": 1,
  "training_example_count": 1,
  "run_fingerprint": "054ee67e2090"
}
```

### 7. Evaluation Output

`evaluate` and `verify` emit a metrics object. `verify` fails if schema validity, provenance, F1, or hallucination thresholds fall outside the configured bounds.

```json
{
  "metrics": {
    "schema_validity_rate": 1.0,
    "provenance_rate": 1.0,
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0,
    "hallucinated_preference_rate": 0.0,
    "true_positive": 15.0,
    "false_positive": 0.0,
    "false_negative": 0.0
  },
  "errors": []
}
```

## Why This Step

Video generation, posting, analytics, and UI display prove orchestration. This pipeline proves whether the harness can accumulate user taste over time without corrupting memory. It is the part most worth evaluating deeply because it decides whether the agent becomes more useful after each interaction.
