ALTER TABLE algo.experiment_runs
    ADD COLUMN IF NOT EXISTS training_duration_seconds Float32 DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS data_start_utc DateTime('UTC') DEFAULT toDateTime('1970-01-01 00:00:00', 'UTC'),
    ADD COLUMN IF NOT EXISTS data_end_utc DateTime('UTC') DEFAULT toDateTime('1970-01-01 00:00:00', 'UTC'),
    ADD COLUMN IF NOT EXISTS model_artifact_id String DEFAULT ''
