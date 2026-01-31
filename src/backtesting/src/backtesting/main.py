from backtesting.configs.experiment import ExperimentConfig
from backtesting.engine.runner import BacktestRunner


def main() -> None:
    config = ExperimentConfig(
        data_path='src/backtesting/src/backtesting/data/DE_data.csv',
        model_name='lear',
        calibration_window=7 * 24,
        train_test_split=0.8,
        target_column='price',
        date_column='date',
        results_dir='results'
    )
    
    runner = BacktestRunner(config)
    runner.run()


if __name__ == "__main__":
    main()
