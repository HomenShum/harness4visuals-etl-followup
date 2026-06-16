# Pioneer / Fastino Integration

Pioneer is the Fastino Labs platform for fine-tuning, evaluating, and deploying small language models and LLM adapters. In this harness, Pioneer is the target for turning curated creative-agent history into decoder SFT data.

The repo keeps the provider-facing training rows clean and puts provenance in a companion manifest. That matters because chat SFT providers generally expect strict `messages` rows, while the harness still needs traceability back to preference signals and chat turns.

## Official References

- [Pioneer introduction](https://docs.pioneer.ai/introduction): lifecycle is upload data, run inference, fine-tune, evaluate, deploy.
- [Pioneer quickstart](https://docs.pioneer.ai/quickstart): API keys use the `X-API-Key` header and should stay out of version control.
- [Pioneer LLM fine-tuning guide](https://docs.pioneer.ai/guides/fine-tune-llm): SFT, GRPO, and DPO use `POST /felix/training-jobs` with `training_algorithm`.
- [Pioneer training jobs API](https://docs.pioneer.ai/api-reference/training-jobs): start, poll, stop, and download training jobs.
- [Pioneer machine-readable docs](https://agent.pioneer.ai/llms.txt): dataset upload flow, dataset formats, OpenAI-compatible endpoints, and model catalog.

## Export Files

```bash
python -m agent_taste_etl.cli export-pioneer \
  --input examples/long_multiturn_chat_history.json \
  --out out/pioneer \
  --dataset-name harness4visuals_preference_sft \
  --model-name harness4visuals-preference-prompt-adapter \
  --base-model Qwen/Qwen3-8B
```

This writes:

- `decoder_sft.jsonl`: provider-clean chat SFT rows.
- `dataset_manifest.json`: harness provenance and dataset intent.
- `dataset_upload_request.json`: body for the presigned upload URL request.
- `training_job_request.json`: body for `POST /felix/training-jobs`.

## SFT Row Shape

Pioneer decoder SFT accepts chat rows with `messages`. The harness writes one JSON object per line:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You transform messy creative-agent chat history into faithful, provenance-backed social generation prompts..."
    },
    {
      "role": "user",
      "content": "{\n  \"input\": {\n    \"chat_summary\": \"...\",\n    \"taste_signals\": []\n  },\n  \"instruction\": \"...\",\n  \"metadata\": {\n    \"source_signal_ids\": [],\n    \"source_turn_ids\": []\n  }\n}"
    },
    {
      "role": "assistant",
      "content": "{\"prompt\":\"Generate a social content concept...\",\"target\":\"social_generation_prompt\"}"
    }
  ]
}
```

The provider row intentionally contains only `messages`. Keep `dataset_manifest.json` beside the uploaded dataset for source traceability.

## Upload Flow

Pioneer uses a presigned upload flow for datasets.

```bash
export PIONEER_API_KEY="pio_sk_..."

curl -X POST https://api.pioneer.ai/felix/datasets/upload/url \
  -H "X-API-Key: $PIONEER_API_KEY" \
  -H "Content-Type: application/json" \
  -d @out/pioneer/dataset_upload_request.json
```

Use the returned presigned URL to upload the JSONL file:

```bash
curl -X PUT "$PRESIGNED_URL" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @out/pioneer/decoder_sft.jsonl
```

Then trigger processing with the returned dataset ID:

```bash
curl -X POST https://api.pioneer.ai/felix/datasets/upload/process \
  -H "X-API-Key: $PIONEER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":"DATASET_ID"}'
```

## Training Job

After the dataset is ready:

```bash
curl -X POST https://api.pioneer.ai/felix/training-jobs \
  -H "X-API-Key: $PIONEER_API_KEY" \
  -H "Content-Type: application/json" \
  -d @out/pioneer/training_job_request.json
```

The generated request uses:

```json
{
  "model_name": "harness4visuals-preference-prompt-adapter",
  "base_model": "Qwen/Qwen3-8B",
  "datasets": [{"name": "harness4visuals_preference_sft"}],
  "training_type": "lora",
  "training_algorithm": "sft",
  "nr_epochs": 3,
  "learning_rate": 0.00005,
  "batch_size": 4
}
```

Pioneer docs say decoder LLM training is LoRA-only, while full fine-tuning is reserved for GLiNER encoder models. For this harness, the right default is decoder `sft` because the model is learning to imitate the desired prompt-transformation behavior.

## Evaluation Loop

Use Pioneer evaluation after training, but keep the harness evaluation as a preflight gate:

1. Run `python -m agent_taste_etl.cli verify`.
2. Export `decoder_sft.jsonl`.
3. Upload dataset and train in Pioneer.
4. Run Pioneer evaluation against held-out records.
5. Compare model output to base model, especially on:
   - durable versus campaign scope separation
   - hallucinated preference rate
   - correct negative preference preservation
   - prompt usefulness for image/video generation

## When To Use GLiNER Instead

Use Pioneer GLiNER/NER training when the target task is extracting structured labels from raw chat text:

- detect preference entities
- classify durable versus campaign scope
- classify visual, voice, trust, or aesthetic signal type

Use decoder SFT when the target task is rewriting the full messy conversation into a final model-ready prompt or training example.

For this repo, decoder SFT is the primary path. GLiNER is a good future improvement for replacing the deterministic extractor with a trained lightweight classifier/extractor.
