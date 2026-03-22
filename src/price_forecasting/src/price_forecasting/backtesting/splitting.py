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
