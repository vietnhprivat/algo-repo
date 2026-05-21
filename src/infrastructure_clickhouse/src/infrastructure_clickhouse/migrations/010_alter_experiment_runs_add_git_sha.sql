ALTER TABLE algo.experiment_runs
    ADD COLUMN IF NOT EXISTS git_sha String DEFAULT '';
