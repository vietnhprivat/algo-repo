"""Live predict-path tests.

A genuine day-ahead forecast must be producible *before* the target day's
actual price is published. Inference never consumes the target value (the
engine trains on ``features.index < target_date`` and predicts from the target
feature row only), so a missing/NaN target actual must neither block the
forecast nor change it.
"""

import numpy as np
import pandas as pd

from price_forecasting.configs.experiment import ExperimentConfig
from price_forecasting.live_runner import LiveRunner
from tests.price_forecasting.conftest import make_hourly_dataframe

N_PERIODS = 24
TARGET_DAY = "2019-04-20"


def _lear_config(tmp_path) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="predict_path_test",
        results_dir=str(tmp_path / "results"),
        area="DE",
        target_column="price",
        train_ratio=0.5,
        validation_ratio=0.0,
        test_ratio=0.5,
        calibration_windows=[30],
        refit_interval_days=1,
        model_type="lear",
        exogenous_curve_types=["load"],
        model_params={"alpha": "auto"},
        target_scaler="asinh",
        resample_to_hourly=False,
    )


def _frame_with_target_actual(target_actual: float | None) -> pd.DataFrame:
    """Hourly frame whose target-day price is set to ``target_actual``.

    ``None`` simulates 'the day-ahead auction has not cleared yet', i.e. the
    target day's actual price is not in the data. Exogenous values for the
    target day (published ahead) and all price lags (past) remain present.
    """
    df = make_hourly_dataframe(
        start_date="2019-01-01",
        end_date="2019-04-21",
        exogenous_columns=["load"],
    )
    day = pd.Timestamp(TARGET_DAY)
    mask = (df.index >= day) & (df.index < day + pd.Timedelta(days=1))
    df.loc[mask, "price"] = np.nan if target_actual is None else target_actual
    return df


def _predict(tmp_path, target_actual: float | None) -> np.ndarray:
    result = LiveRunner(_lear_config(tmp_path)).run_live_with_metadata(
        TARGET_DAY, dataframe=_frame_with_target_actual(target_actual)
    )
    return result.prediction.to_numpy()


class TestLivePredictPath:
    def test_predicts_when_target_actual_missing(self, tmp_path):
        """Forecast succeeds even though the target day's actual is absent."""
        prediction = _predict(tmp_path, target_actual=None)
        assert prediction.shape[0] == N_PERIODS
        assert np.isfinite(prediction).all()

    def test_target_actual_does_not_change_prediction(self, tmp_path):
        """Prediction is identical whether the actual is missing or any value."""
        missing = _predict(tmp_path, target_actual=None)
        high = _predict(tmp_path, target_actual=9999.0)
        low = _predict(tmp_path, target_actual=-9999.0)
        np.testing.assert_array_equal(high, low)
        np.testing.assert_array_equal(missing, high)


class TestLatestForecastableTarget:
    """With no explicit target_date, forecast the most recent day whose inputs
    are complete — never break on a partially-available leading-edge day."""

    def test_target_none_resolves_to_latest_complete_day(self, tmp_path):
        df = make_hourly_dataframe(
            start_date="2019-01-01", end_date="2019-04-21", exogenous_columns=["load"]
        )
        # Make the most recent day's exogenous incomplete -> not forecastable;
        # the latest *complete* day is then the one before it.
        last = pd.Timestamp("2019-04-20")
        last_mask = (df.index >= last) & (df.index < last + pd.Timedelta(days=1))
        df.loc[last_mask, "load"] = np.nan

        result = LiveRunner(_lear_config(tmp_path)).run_live_with_metadata(
            target_date=None, dataframe=df
        )

        assert result.target_date == "2019-04-19"
        assert len(result.prediction) == N_PERIODS
