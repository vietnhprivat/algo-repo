CREATE TABLE IF NOT EXISTS algo.drift_reports
(
    report_id            String,
    created_utc          DateTime('UTC') DEFAULT now(),
    area                 LowCardinality(String),
    curve_name           LowCardinality(String),
    reference_start_utc  DateTime('UTC'),
    reference_end_utc    DateTime('UTC'),
    current_start_utc    DateTime('UTC'),
    current_end_utc      DateTime('UTC'),
    stat_test            LowCardinality(String),
    drift_score          Float64,
    drift_threshold      Float64,
    drift_detected       UInt8,
    reference_n          UInt32,
    current_n            UInt32
)
ENGINE = ReplacingMergeTree(created_utc)
PARTITION BY toStartOfQuarter(created_utc)
ORDER BY (area, curve_name, report_id)
