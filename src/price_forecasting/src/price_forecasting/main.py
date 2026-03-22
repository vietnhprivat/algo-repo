from price_forecasting import BacktestRunner, ExperimentConfig


def main() -> None:
    config = ExperimentConfig(
        experiment_name="local_backtest",
        results_dir="results",
        area="DE",
        target_column="price",
        model_type="lear",
        model_params={"alpha": 0.01},
        exogenous_curve_types=["TotalLoad"],
        train_ratio=0.7,
        validation_ratio=0.15,
        test_ratio=0.15,
        calibration_windows=[56, 84, 352],
        refit_interval_days=1,
    )

    runner = BacktestRunner(config)
    outputs = runner.execute()
    print("Backtest forecast sample:")
    print(outputs["forecasts"].head())


if __name__ == "__main__":
    main()
