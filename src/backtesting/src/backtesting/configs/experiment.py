from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class ExperimentConfig:
    data_path: str
    model_name: str
    calibration_window: int = 7 * 24
    train_test_split: float = 0.8
    target_column: str = "Price"
    date_column: str = "Date"
    feature_columns: Optional[List[str]] = None
    model_params: Dict[str, Any] = field(default_factory=dict)
    results_dir: str = "results"

    def __post_init__(self) -> None:
        if self.feature_columns is None:
            self.feature_columns = []
