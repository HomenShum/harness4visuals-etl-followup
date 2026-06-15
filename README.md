# Agent Taste ETL Harness

This repo follows up on the highest-leverage step in the agent workflow:

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

## Why This Step

Video generation, posting, analytics, and UI display prove orchestration. This pipeline proves whether the harness can accumulate user taste over time without corrupting memory. It is the part most worth evaluating deeply because it decides whether the agent becomes more useful after each interaction.
