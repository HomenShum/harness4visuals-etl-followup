# ClickHouse Integration

ClickHouse is the right fit for the harness memory layer when the question is analytical:

- How did a user's taste change across creative sessions?
- Which generated assets caused negative feedback?
- Which prompt transforms improve acceptance rate?
- Which training examples came from durable preferences versus campaign-only instructions?

The export path is intentionally append-only. Every ETL run writes a new run row, signal rows, prompt rows, and training rows. Do not update preference rows in place; use query-time aggregation or downstream materialized views when you want "latest taste profile" behavior.

## Official References

- [JSONEachRow](https://clickhouse.com/docs/interfaces/formats/JSONEachRow): ClickHouse's newline-delimited JSON format, also aliased as `JSONLines`, `NDJSON`, and `JSONL`.
- [Python integration with ClickHouse Connect](https://clickhouse.com/docs/integrations/python): official Python client using `command`, `insert`, and `query`.
- [MergeTree engine](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree): core table engine for high-ingest analytical tables.
- [Working with JSON](https://clickhouse.com/docs/integrations/data-formats/json/loading): loading JSON files and mapping JSON keys to table columns.

## Files

```bash
python -m agent_taste_etl.cli export-clickhouse \
  --input examples/long_multiturn_chat_history.json \
  --out out/clickhouse \
  --conversation-id conv_h4v_launch_video_001 \
  --user-id user_demo \
  --dataset-name harness4visuals_preference_sft
```

This writes:

- `runs.jsonl`
- `preference_signals.jsonl`
- `prompt_records.jsonl`
- `training_examples.jsonl`

The SQL schema lives at [schemas/clickhouse/harness4visuals.sql](../../schemas/clickhouse/harness4visuals.sql).

## Load With clickhouse-client

```bash
clickhouse-client --queries-file schemas/clickhouse/harness4visuals.sql

clickhouse-client --query \
  "INSERT INTO harness4visuals.etl_runs FORMAT JSONEachRow" \
  < out/clickhouse/runs.jsonl

clickhouse-client --query \
  "INSERT INTO harness4visuals.preference_signals FORMAT JSONEachRow" \
  < out/clickhouse/preference_signals.jsonl

clickhouse-client --query \
  "INSERT INTO harness4visuals.prompt_records FORMAT JSONEachRow" \
  < out/clickhouse/prompt_records.jsonl

clickhouse-client --query \
  "INSERT INTO harness4visuals.training_examples FORMAT JSONEachRow" \
  < out/clickhouse/training_examples.jsonl
```

## Load With Python

```python
import json
from pathlib import Path

import clickhouse_connect

client = clickhouse_connect.get_client(
    host="HOSTNAME.clickhouse.cloud",
    port=8443,
    username="default",
    password="CLICKHOUSE_PASSWORD",
)

schema_sql = Path("schemas/clickhouse/harness4visuals.sql").read_text()
for statement in [part.strip() for part in schema_sql.split(";") if part.strip()]:
    client.command(statement)

tables = {
    "etl_runs": {
        "file": "runs.jsonl",
        "columns": [
            "run_id",
            "conversation_id",
            "user_id",
            "pipeline",
            "version",
            "input_turns",
            "signal_count",
            "prompt_count",
            "training_example_count",
            "run_fingerprint",
            "manifest_json",
        ],
    },
    "preference_signals": {
        "file": "preference_signals.jsonl",
        "columns": [
            "run_id",
            "conversation_id",
            "user_id",
            "signal_id",
            "kind",
            "subject",
            "polarity",
            "scope",
            "confidence",
            "weight",
            "evidence",
            "source_turn_ids",
            "payload_json",
        ],
    },
    "prompt_records": {
        "file": "prompt_records.jsonl",
        "columns": [
            "run_id",
            "conversation_id",
            "user_id",
            "prompt_id",
            "target",
            "prompt",
            "source_signal_ids",
            "payload_json",
        ],
    },
    "training_examples": {
        "file": "training_examples.jsonl",
        "columns": [
            "run_id",
            "conversation_id",
            "user_id",
            "dataset_name",
            "example_id",
            "format",
            "instruction",
            "input_json",
            "output_json",
            "source_turn_ids",
            "source_signal_ids",
            "payload_json",
        ],
    },
}

for table, spec in tables.items():
    rows = [
        json.loads(line)
        for line in Path("out/clickhouse", spec["file"]).read_text().splitlines()
        if line.strip()
    ]
    client.insert(
        f"harness4visuals.{table}",
        [[row[column] for column in spec["columns"]] for row in rows],
        column_names=spec["columns"],
    )
```

## Query Patterns

Durable user taste:

```sql
SELECT
    kind,
    subject,
    polarity,
    max(confidence) AS confidence,
    groupUniqArrayArray(source_turn_ids) AS source_turn_ids
FROM harness4visuals.preference_signals
WHERE user_id = 'user_demo'
  AND scope = 'durable'
GROUP BY kind, subject, polarity
ORDER BY kind, subject;
```

Campaign-only constraints that should not become durable memory:

```sql
SELECT subject, polarity, evidence, source_turn_ids
FROM harness4visuals.preference_signals
WHERE user_id = 'user_demo'
  AND conversation_id = 'conv_h4v_launch_video_001'
  AND scope = 'campaign'
ORDER BY inserted_at;
```

Training rows with traceability back to source turns:

```sql
SELECT
    dataset_name,
    example_id,
    source_turn_ids,
    source_signal_ids,
    output_json
FROM harness4visuals.training_examples
WHERE dataset_name = 'harness4visuals_preference_sft';
```

## Why These Keys

The tables use `MergeTree` because this data is append-heavy and analytical. Partitions are monthly via `toYYYYMM(inserted_at)` so partitions do not become too granular. `ORDER BY` starts with `user_id` and `conversation_id` because most harness queries retrieve memory for one user, one session, or one dataset.

## Production Guidance

- Keep raw provider payloads in object storage if they are large; store stable `asset_id` and `uri` in ClickHouse.
- Use ClickHouse for analytical memory and training selection, not as the blob store for image/video bytes.
- Preserve `payload_json` even when typed columns exist. It gives you forward compatibility when the signal schema evolves.
- Add materialized views only after you know your query patterns. The base append-only tables are easier to audit.
- Avoid storing API keys, private media URLs, or unreduced PII in evidence fields.
