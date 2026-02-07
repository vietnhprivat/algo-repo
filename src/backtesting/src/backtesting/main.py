from backtesting.configs.experiment import ExperimentConfig
from backtesting.runner import BacktestRunner, LiveRunner

def main() -> None:
    config = ExperimentConfig(
        experiment_name="local_backtest",
        results_dir="results",
        data_path="src/backtesting/src/backtesting/data/DE_data.csv",
        target_column="price",
        model_type="lear",
        model_params={"alpha": 0.01},
        exogenous_features=[],
        test_start_date="2017-12-01",
        test_end_date="2017-12-31",
        calibration_windows=[56, 84, 352],
        refit_interval_days=1,
    )

    live_runner = LiveRunner(config)
    live_prediction = live_runner.run_live("2017-12-31")
    print("Live prediction sample:")
    print(live_prediction.head())

    runner = BacktestRunner(config)
    outputs = runner.execute()
    print("Backtest forecast sample:")
    print(outputs["forecasts"].head())

if __name__ == "__main__":
    main()
