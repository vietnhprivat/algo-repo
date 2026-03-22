CREATE TABLE IF NOT EXISTS algo.experiment_predictions
(
    run_id        UUID,
    timestamp_utc DateTime('UTC'),
    actual        Float32,
    predicted     Float32
)
ENGINE = ReplacingMergeTree()
ORDER BY (run_id, timestamp_utc)
PARTITION BY toStartOfQuarter(timestamp_utc)
