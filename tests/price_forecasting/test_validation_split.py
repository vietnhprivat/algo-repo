import numpy as np
import pandas as pd
import pytest

from price_forecasting.backtesting.splitting import split_by_dates_with_validation


def _features_targets(n_days: int = 100):
    idx = pd.date_range("2024-01-01", periods=n_days, freq="D")
    features = pd.DataFrame(np.zeros((n_days, 3)), index=idx)
    targets = pd.DataFrame(np.zeros((n_days, 24)), index=idx)
    return features, targets


class TestValidationSplit:
    def test_validation_window_is_disjoint_from_train_and_test(self):
        features, targets = _features_targets()
        splits = split_by_dates_with_validation(
            features, targets,
            val_start="2024-02-15", val_end="2024-03-05",
            test_start="2024-03-15", test_end="2024-04-05",
        )
        assert splits.train_features.index.max() < pd.Timestamp("2024-02-15")
        assert (splits.val_features.index >= pd.Timestamp("2024-02-15")).all()
        assert (splits.val_features.index <= pd.Timestamp("2024-03-05")).all()
        assert splits.test_features.index.min() >= pd.Timestamp("2024-03-15")
        # No overlap
        assert splits.val_features.index.intersection(splits.test_features.index).empty
        assert splits.train_features.index.intersection(splits.val_features.index).empty

    def test_rejects_overlapping_val_and_test(self):
        features, targets = _features_targets()
        with pytest.raises(ValueError, match="val_end must precede test_start"):
            split_by_dates_with_validation(
                features, targets,
                val_start="2024-02-15", val_end="2024-03-20",
                test_start="2024-03-15", test_end="2024-04-05",
            )

    def test_targets_are_split_to_match_features(self):
        features, targets = _features_targets()
        splits = split_by_dates_with_validation(
            features, targets,
            val_start="2024-02-15", val_end="2024-03-05",
            test_start="2024-03-15", test_end="2024-04-05",
        )
        assert splits.train_targets.index.equals(splits.train_features.index)
        assert splits.val_targets.index.equals(splits.val_features.index)
        assert splits.test_targets.index.equals(splits.test_features.index)
