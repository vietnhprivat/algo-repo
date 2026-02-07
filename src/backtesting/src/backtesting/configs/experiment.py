from dataclasses import dataclass, field

from datetime import timedelta
from typing import List, Dict, Any
import yaml

@dataclass
class ExperimentConfig:
    experiment_name: str
    results_dir: str
    data_path: str
    target_column: str = "price"    
    test_start_date: str = "2019-01-01"
    test_end_date: str = "2019-12-31"
    
    """LEAR Benchmark uses [56, 84, 1092, 1456]"""
    calibration_windows: List[int] = field(default_factory=lambda: [56, 84, 1092, 1456])
    
    """Optimization: Retrain every N days (1 for LEAR, 7 for DNN)"""
    refit_interval_days: int = 1

    model_type: str = "LEAR"
    
    """Specific args passed to the model class (e.g. {'alpha': 0.1} or {'layers': [256, 24]})"""
    exogenous_features: list[str] = field(default_factory=list)
    model_params: Dict[str, Any] = field(default_factory=dict)

    # @classmethod
    # def load(cls, path: str) -> "ExperimentConfig":
    #     with open(path, "r") as f:
    #         return cls(**yaml.safe_load(f))
    
