from attr import dataclass


@dataclass
class Configurations:
    data_directory: str = "src/backtesting/src/backtesting/data"
    results_path: str = "src/backtesting/src/backtesting/results"


configs: Configurations = Configurations()
