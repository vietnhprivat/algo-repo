from backtesting.configs.experiment import ExperimentConfig
from backtesting.runner import BacktestRunner

def main() -> None:
    config = ExperimentConfig(
        experiment_name="local_backtest",
        results_dir="results",
        data_path="src/backtesting/src/backtesting/data/DE_data.csv",
        target_column="price",
        model_type="LEAR",
        model_params={"alpha": 0.01},
        exogenous_features=[],
        test_start_date="2019-01-01",
        test_end_date="2019-12-31",
    )

    runner = BacktestRunner(config)
    outputs = runner.execute()
    print(outputs["forecasts"].head())

if __name__ == "__main__":
    main()



import pandas as pd
df = pd.DataFrame({
    'timestamp': pd.date_range(start='2019-01-01', periods=100, freq='D'),
    'price': range(100),
    'exogenous_1': range(100, 200),
    'exogenous_2': range(200, 300),
}) 

