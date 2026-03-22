from dataclasses import dataclass

import pandas as pd


@dataclass
class DatasetSplit:
    features: pd.DataFrame
    targets: pd.DataFrame

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.features.index


@dataclass
class SplitResult:
    train: DatasetSplit
    validation: DatasetSplit
    test: DatasetSplit


def split_dataset(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
) -> SplitResult:
    """Split features and targets chronologically by ratio.

    Args:
        features: DataFrame with DatetimeIndex (daily rows).
        targets: DataFrame with DatetimeIndex (daily rows), aligned with features.
        train_ratio: Fraction of data for training (e.g. 0.7).
        validation_ratio: Fraction of data for validation (e.g. 0.15).
        test_ratio: Fraction of data for testing (e.g. 0.15).

    Returns:
        SplitResult with train, validation, and test DatasetSplits.
    """
    total = round(train_ratio + validation_ratio + test_ratio, 10)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"Split ratios must sum to 1.0, got {total} "
            f"({train_ratio} + {validation_ratio} + {test_ratio})"
        )

    features = features.sort_index()
    targets = targets.sort_index()

    n = len(features)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + validation_ratio))

    return SplitResult(
        train=DatasetSplit(
            features=features.iloc[:train_end],
            targets=targets.iloc[:train_end],
        ),
        validation=DatasetSplit(
            features=features.iloc[train_end:val_end],
            targets=targets.iloc[train_end:val_end],
        ),
        test=DatasetSplit(
            features=features.iloc[val_end:],
            targets=targets.iloc[val_end:],
        ),
    )
