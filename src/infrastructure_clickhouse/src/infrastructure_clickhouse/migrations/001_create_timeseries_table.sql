CREATE TABLE IF NOT EXISTS algo.timeseries
(
    source        LowCardinality(String),
    curve_name    String,
    area          LowCardinality(String),
    timezone      LowCardinality(String),
    timestamp_utc DateTime('UTC'),
    value         Float32,
    ingested_utc  DateTime('UTC')
)
ENGINE = ReplacingMergeTree(ingested_utc)
ORDER BY (curve_name, timestamp_utc)
PARTITION BY toStartOfQuarter(timestamp_utc)
