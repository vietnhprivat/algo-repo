CREATE TABLE IF NOT EXISTS algo.experiment_runs
(
    run_id          UUID,
    created_utc     DateTime('UTC'),
    experiment_name LowCardinality(String),
    area            LowCardinality(String),
    model_type      LowCardinality(String),
    config_json     String,
    metrics_json    String
)
ENGINE = ReplacingMergeTree(created_utc)
ORDER BY (run_id)
