CREATE TABLE IF NOT EXISTS algo.model_artifacts
(
    artifact_id         String,
    created_utc         DateTime('UTC'),
    run_id              String,
    area                LowCardinality(String),
    model_type          LowCardinality(String),
    config_name         LowCardinality(String),
    artifact_blob       String,
    artifact_size_bytes UInt32
)
ENGINE = ReplacingMergeTree(created_utc)
ORDER BY (artifact_id)
