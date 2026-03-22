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
    if abs(train_ratio + validation_ratio + test_ratio - 1.0) > 1e-6:
        raise ValueError(
            f"Ratios must sum to 1.0, got {train_ratio + validation_ratio + test_ratio}"
        )

    n = len(features)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + validation_ratio))

    return SplitResult(
        train=DatasetSplit(features.iloc[:train_end], targets.iloc[:train_end]),
        validation=DatasetSplit(
            features.iloc[train_end:val_end], targets.iloc[train_end:val_end]
        ),
        test=DatasetSplit(features.iloc[val_end:], targets.iloc[val_end:]),
    )


def split_by_dates(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    test_start_date: str,
    test_end_date: str,
) -> SplitResult:
    """Split by explicit date range.

    Training data = everything strictly before test_start_date.
    Test data = [test_start_date, test_end_date] inclusive.
    Validation is empty (not meaningful with explicit test dates).
    """
    test_start = pd.Timestamp(test_start_date)
    test_end = pd.Timestamp(test_end_date)

    if test_start > test_end:
        raise ValueError(
            f"test_start_date ({test_start_date}) must be before test_end_date ({test_end_date})"
        )

    index : pd.DatetimeIndex = features.index
    train_mask = index < test_start
    test_mask = (index >= test_start) & (index <= test_end)

    if not test_mask.any():
        raise ValueError(
            f"No data found in test range [{test_start_date}, {test_end_date}]. "
            f"Available data: {index[0].date()} to {index[-1].date()}"
        )

    empty = DatasetSplit(features.iloc[:0], targets.iloc[:0])

    return SplitResult(
        train=DatasetSplit(features[train_mask], targets[train_mask]),
        validation=empty,
        test=DatasetSplit(features[test_mask], targets[test_mask]),
    )
