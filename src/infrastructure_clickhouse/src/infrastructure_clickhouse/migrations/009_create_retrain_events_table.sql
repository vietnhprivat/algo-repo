CREATE TABLE IF NOT EXISTS algo.retrain_events
(
    event_id          String,
    created_utc       DateTime64(3, 'UTC'),
    triggered_by      String,
    area              String,
    config_name       String,
    drift_report_id   Nullable(String),
    status            String,
    completed_utc     Nullable(DateTime64(3, 'UTC')),
    new_run_id        Nullable(String),
    notes             Nullable(String)
)
ENGINE = ReplacingMergeTree(created_utc)
ORDER BY event_id;
