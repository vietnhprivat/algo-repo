from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class ExperimentConfig:
    experiment_name: str
    data_path: str
    results_dir: str
    test_start: str
    test_end: str
    calibration_windows: List[int]
    refit_interval: int = 1
    model_type: str = "LEAR"
    model_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "ExperimentConfig":
        pass