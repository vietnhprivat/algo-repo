from dataclasses import dataclass, field

from typing import List, Dict, Any


@dataclass
class ExperimentConfig:
    experiment_name: str
    results_dir: str
    area: str

    target_column: str = "price"

    # Data split ratios (must sum to 1.0)
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15

    """LEAR Benchmark uses [56, 84, 1092, 1456]"""
    calibration_windows: List[int] = field(default_factory=lambda: [56, 84, 1092, 1456])

    """Optimization: Retrain every N days (1 for LEAR, 7 for DNN)"""
    refit_interval_days: int = 1

    model_type: str = "LEAR"

    # Exogenous forecast curve types from algo.forecasts
    # e.g. ["TotalLoad", "Generation", "Solar"]
    exogenous_curve_types: list[str] = field(default_factory=list)

    """Specific args passed to the model class (e.g. {'alpha': 0.1} or {'layers': [256, 24]})"""
    model_params: Dict[str, Any] = field(default_factory=dict)
