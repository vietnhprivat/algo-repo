CREATE TABLE IF NOT EXISTS algo.forecasts
(
    source               LowCardinality(String),
    curve_name           String,
    area                 LowCardinality(String),
    area_timezone        LowCardinality(String),
    model                LowCardinality(String),
    issued_utc           DateTime('UTC'),
    issued_timezone      LowCardinality(String),
    timestamp_utc        DateTime('UTC'),
    value                Float32,
    ingested_utc         DateTime('UTC')
)
ENGINE = ReplacingMergeTree(ingested_utc)
ORDER BY (curve_name, model, issued_utc, timestamp_utc)
PARTITION BY toStartOfQuarter(timestamp_utc)
