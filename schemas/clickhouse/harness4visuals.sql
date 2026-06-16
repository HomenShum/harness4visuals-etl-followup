CREATE DATABASE IF NOT EXISTS harness4visuals;

CREATE TABLE IF NOT EXISTS harness4visuals.etl_runs
(
    inserted_at DateTime64(3) DEFAULT now64(3),
    run_id String,
    conversation_id String,
    user_id String,
    pipeline LowCardinality(String),
    version LowCardinality(String),
    input_turns UInt32,
    signal_count UInt32,
    prompt_count UInt32,
    training_example_count UInt32,
    run_fingerprint String,
    manifest_json String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(inserted_at)
ORDER BY (user_id, conversation_id, run_id);

CREATE TABLE IF NOT EXISTS harness4visuals.preference_signals
(
    inserted_at DateTime64(3) DEFAULT now64(3),
    run_id String,
    conversation_id String,
    user_id String,
    signal_id String,
    kind LowCardinality(String),
    subject String,
    polarity Enum8('positive' = 1, 'negative' = -1),
    scope LowCardinality(String),
    confidence Float32,
    weight Float32,
    evidence String,
    source_turn_ids Array(String),
    payload_json String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(inserted_at)
ORDER BY (user_id, conversation_id, scope, kind, signal_id);

CREATE TABLE IF NOT EXISTS harness4visuals.prompt_records
(
    inserted_at DateTime64(3) DEFAULT now64(3),
    run_id String,
    conversation_id String,
    user_id String,
    prompt_id String,
    target LowCardinality(String),
    prompt String,
    source_signal_ids Array(String),
    payload_json String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(inserted_at)
ORDER BY (user_id, conversation_id, target, prompt_id);

CREATE TABLE IF NOT EXISTS harness4visuals.training_examples
(
    inserted_at DateTime64(3) DEFAULT now64(3),
    run_id String,
    conversation_id String,
    user_id String,
    dataset_name String,
    example_id String,
    format LowCardinality(String),
    instruction String,
    input_json String,
    output_json String,
    source_turn_ids Array(String),
    source_signal_ids Array(String),
    payload_json String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(inserted_at)
ORDER BY (user_id, dataset_name, conversation_id, example_id);
