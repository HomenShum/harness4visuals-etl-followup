# Training Targets and Alternatives

The harness should not depend on one training provider. It emits a canonical internal `training.jsonl`, then exports provider-specific shapes.

## Canonical Internal Shape

`training.jsonl` keeps the richest harness context:

```json
{
  "instruction": "Transform messy agent chat history into a faithful, provenance-backed social generation prompt...",
  "input": {
    "chat_summary": "...",
    "taste_signals": []
  },
  "output": {
    "target": "social_generation_prompt",
    "prompt": "Generate a social content concept..."
  },
  "metadata": {
    "format": "slm_jsonl",
    "source": "chat_history",
    "source_turn_ids": ["turn_001"],
    "source_signal_ids": ["sig_001"]
  }
}
```

Keep this file for auditability. Export provider-specific training files from it.

## Pioneer / Fastino

Use `export-pioneer` for decoder SFT. Pioneer accepts decoder chat SFT rows with `messages`, supports LoRA fine-tuning, and exposes OpenAI-compatible endpoints for serving trained models.

See [pioneer-fastino.md](./pioneer-fastino.md).

## Hugging Face TRL

Hugging Face TRL's `SFTTrainer` supports standard and conversational dataset formats. Conversational rows use:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

That makes `out/pioneer/decoder_sft.jsonl` usable as a starting point for TRL as well. For local experiments, load it with `datasets.load_dataset("json", data_files="decoder_sft.jsonl")` and train with an instruction-tuned base model whose tokenizer has an appropriate chat template.

Reference: [TRL SFTTrainer docs](https://huggingface.co/docs/trl/en/sft_trainer).

## Together AI

Together supports conversational JSONL where each line has a `messages` key with `system`, `user`, and `assistant` roles. It also supports instruction, preference, and generic text formats. If a file contains multiple competing format keys, Together can reject it, so use the provider-clean `decoder_sft.jsonl` rather than the richer internal `training.jsonl`.

References:

- [Together fine-tuning quickstart](https://docs.together.ai/docs/fine-tuning-quickstart)
- [Together data preparation](https://docs.together.ai/docs/fine-tuning-data-preparation)

## OpenAI-Compatible Fine-Tuning

OpenAI model optimization and fine-tuning flows use JSONL datasets and fine-tuning jobs. If you target an OpenAI-compatible provider, prefer the chat `messages` export because it keeps the training example close to the inference-time chat shape.

Reference: [OpenAI model optimization](https://developers.openai.com/api/docs/guides/model-optimization).

## Provider Selection

Use Pioneer/Fastino when:

- you want managed LoRA training and adapter serving for open-source SLMs/LLMs
- you want an OpenAI-compatible inference surface after training
- you may later use GLiNER for signal extraction

Use Hugging Face TRL when:

- you need full control of training code and checkpoints
- you are comfortable managing GPUs and training infrastructure
- you need to inspect or modify the loss/training loop

Use Together or another hosted fine-tuning provider when:

- you want managed training but not a Pioneer-specific lifecycle
- your org already standardizes on their model catalog
- you need provider-native evals, deployment, or billing integration

## Dataset Quality Gates

Before any provider upload:

```bash
python -m unittest discover -s tests
python -m agent_taste_etl.cli verify --out out/verify
python -m agent_taste_etl.cli export-pioneer --out out/pioneer
```

Reject a dataset if:

- provenance is missing
- durable and campaign-only preferences are mixed
- negative preferences are dropped
- a generated prompt references facts not present in the source chat
- JSONL rows fail to parse
- rows contain secrets, private URLs, or raw media bytes
