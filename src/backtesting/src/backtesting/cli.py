import argparse
import yaml
from backtesting.configs.experiment import ExperimentConfig
from backtesting.engine.runner import BacktestRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backtesting experiments")
    parser.add_argument(
        "--config", default="configs/default.yaml", help="Config file path"
    )
    args = parser.parse_args()

    with open(args.config) as f:
        config_dict = yaml.safe_load(f)

    config = ExperimentConfig(**config_dict)
    runner = BacktestRunner(config)
    runner.run()


if __name__ == "__main__":
    main()
