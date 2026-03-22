"""Tests for dataset splitting logic."""

import pytest
import pandas as pd

from price_forecasting.backtesting.splitting import split_dataset, split_by_dates

from tests.price_forecasting.conftest import make_synthetic_features_and_targets


class TestSplitDataset:

    def test_split_ratios_produce_correct_sizes(self):
        features, targets = make_synthetic_features_and_targets(
            start_date="2019-01-01", end_date="2019-03-31"
        )
        # 90 days total
        result = split_dataset(features, targets, 0.7, 0.15, 0.15)

        total = len(result.train.features) + len(result.validation.features) + len(result.test.features)
        assert total == len(features)

        assert len(result.train.features) == int(90 * 0.7)  # 63
        assert len(result.validation.features) == int(90 * 0.85) - int(90 * 0.7)  # 13
        assert len(result.test.features) == 90 - int(90 * 0.85)  # 14

    def test_splits_are_chronological(self):
        features, targets = make_synthetic_features_and_targets()
        result = split_dataset(features, targets, 0.6, 0.2, 0.2)

        assert result.train.dates[-1] < result.validation.dates[0]
        assert result.validation.dates[-1] < result.test.dates[0]

    def test_targets_aligned_with_features(self):
        features, targets = make_synthetic_features_and_targets()
        result = split_dataset(features, targets, 0.7, 0.15, 0.15)

        pd.testing.assert_index_equal(result.train.features.index, result.train.targets.index)
        pd.testing.assert_index_equal(result.validation.features.index, result.validation.targets.index)
        pd.testing.assert_index_equal(result.test.features.index, result.test.targets.index)

    def test_dates_property(self):
        features, targets = make_synthetic_features_and_targets()
        result = split_dataset(features, targets, 0.7, 0.15, 0.15)

        pd.testing.assert_index_equal(result.test.dates, result.test.features.index)

    def test_ratios_must_sum_to_one(self):
        features, targets = make_synthetic_features_and_targets()
        with pytest.raises(ValueError, match="must sum to 1.0"):
            split_dataset(features, targets, 0.5, 0.2, 0.2)

    def test_zero_validation_ratio(self):
        features, targets = make_synthetic_features_and_targets()
        result = split_dataset(features, targets, 0.8, 0.0, 0.2)

        assert len(result.validation.features) == 0
        assert len(result.train.features) > 0
        assert len(result.test.features) > 0


class TestSplitByDates:

    def test_test_dates_are_within_range(self):
        features, targets = make_synthetic_features_and_targets(
            start_date="2019-01-01", end_date="2019-03-31"
        )
        result = split_by_dates(features, targets, "2019-03-01", "2019-03-31")

        assert result.test.dates[0] == pd.Timestamp("2019-03-01")
        assert result.test.dates[-1] == pd.Timestamp("2019-03-31")

    def test_train_is_strictly_before_test_start(self):
        features, targets = make_synthetic_features_and_targets(
            start_date="2019-01-01", end_date="2019-03-31"
        )
        result = split_by_dates(features, targets, "2019-03-01", "2019-03-31")

        assert result.train.dates[-1] < pd.Timestamp("2019-03-01")

    def test_validation_is_empty(self):
        features, targets = make_synthetic_features_and_targets()
        result = split_by_dates(features, targets, "2019-02-15", "2019-02-28")

        assert len(result.validation.features) == 0

    def test_no_data_in_range_raises(self):
        features, targets = make_synthetic_features_and_targets(
            start_date="2019-01-01", end_date="2019-03-31"
        )
        with pytest.raises(ValueError, match="No data found in test range"):
            split_by_dates(features, targets, "2025-01-01", "2025-12-31")

    def test_start_after_end_raises(self):
        features, targets = make_synthetic_features_and_targets()
        with pytest.raises(ValueError, match="must be before"):
            split_by_dates(features, targets, "2019-03-01", "2019-01-01")
