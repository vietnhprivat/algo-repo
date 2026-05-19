CREATE TABLE IF NOT EXISTS algo.hyperparam_trials
(
    study_name        String,
    trial_number      UInt32,
    created_utc       DateTime64(3, 'UTC'),
    area              String,
    model_type        String,
    config_name       String,
    state             String,
    value             Nullable(Float64),
    params_json       String,
    val_start_utc     Nullable(DateTime64(3, 'UTC')),
    val_end_utc       Nullable(DateTime64(3, 'UTC')),
    duration_seconds  Nullable(Float64)
)
ENGINE = ReplacingMergeTree(created_utc)
ORDER BY (study_name, trial_number);
