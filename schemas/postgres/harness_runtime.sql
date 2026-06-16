CREATE TABLE IF NOT EXISTS creative_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    channels JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL,
    current_phase TEXT NOT NULL DEFAULT 'brief',
    iteration INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS harness_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    turn_id TEXT,
    actor TEXT NOT NULL CHECK (actor IN ('user', 'assistant', 'tool', 'system')),
    phase TEXT NOT NULL,
    content JSONB NOT NULL DEFAULT '[]'::jsonb,
    tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider_job_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    asset_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_harness_events_session_created
    ON harness_events(session_id, created_at);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    modality TEXT NOT NULL CHECK (modality IN ('image', 'video', 'audio', 'document')),
    role TEXT NOT NULL CHECK (role IN ('reference', 'generated', 'published')),
    uri TEXT NOT NULL,
    storage_provider TEXT NOT NULL DEFAULT 'object_store',
    mime_type TEXT,
    width INTEGER,
    height INTEGER,
    duration_seconds NUMERIC,
    provider TEXT,
    provider_model TEXT,
    provider_job_id TEXT,
    status TEXT NOT NULL DEFAULT 'available',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assets_session_role
    ON assets(session_id, role);

CREATE TABLE IF NOT EXISTS provider_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_request_id TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    input_json JSONB NOT NULL,
    output_json JSONB,
    error_json JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_provider_jobs_session_status
    ON provider_jobs(session_id, status);

CREATE TABLE IF NOT EXISTS asset_reviews (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    reviewer_user_id TEXT NOT NULL,
    selected_asset_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    rejected_asset_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_text TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK (approval_status IN ('needs_revision', 'approved_for_post', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_asset_reviews_session_created
    ON asset_reviews(session_id, created_at);

CREATE TABLE IF NOT EXISTS post_records (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'composio_instagram',
    channel TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_asset_ids JSONB NOT NULL,
    caption TEXT NOT NULL,
    external_post_id TEXT,
    permalink TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft', 'scheduled', 'published', 'failed')),
    provider_job_id TEXT REFERENCES provider_jobs(id),
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_post_records_session_status
    ON post_records(session_id, status);

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    post_record_id TEXT NOT NULL REFERENCES post_records(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'composio_instagram',
    metrics_json JSONB NOT NULL,
    comments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_post_fetched
    ON analytics_snapshots(post_record_id, fetched_at);

CREATE TABLE IF NOT EXISTS runtime_etl_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES creative_sessions(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    signal_count INTEGER NOT NULL DEFAULT 0,
    prompt_count INTEGER NOT NULL DEFAULT 0,
    training_example_count INTEGER NOT NULL DEFAULT 0,
    manifest_json JSONB,
    clickhouse_export_uri TEXT,
    pioneer_export_uri TEXT,
    error_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_runtime_etl_runs_session_status
    ON runtime_etl_runs(session_id, status);
