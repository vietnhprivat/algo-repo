from dataclasses import dataclass, field

from typing import List, Dict, Any, Optional


@dataclass
class ExperimentConfig:
    experiment_name: str
    results_dir: str
    area: str

    target_column: str = "price"

    # Option A: explicit test date range (recommended)
    # Training data = everything before test_start_date
    # Test data = [test_start_date, test_end_date]
    test_start_date: Optional[str] = None
    test_end_date: Optional[str] = None

    # Validation window (recommended: disjoint, ends before test_start_date).
    # Lago et al. 2021 §4.3.2 use 42 weeks; checklist #9 requires this be
    # different from the test set when hyperparameters are selected ex-ante.
    val_start_date: Optional[str] = None
    val_end_date: Optional[str] = None

    # Option B: ratio-based split (fallback when test dates not set)
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

    # Custom feature transformers. If None, DataPreprocessor builds model-type defaults.
    # If set, must be a list of FeatureTransformer instances.
    feature_transformers: Optional[list] = None

    # Target scaler — "standard" (default, backwards compatible) or "asinh"
    # (Lago et al. 2021 §4.2, recommended for LEAR).
    target_scaler: str = "standard"

    # Number of DNN replicates to average at serving time (Lago §4.4).
    # Only used for model_type == "dnn".
    n_dnn_ensemble: int = 1
