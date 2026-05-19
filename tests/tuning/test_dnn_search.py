import optuna

from price_forecasting.tuning.dnn_search import build_dnn_search_space


class TestDnnSearchSpace:
    def test_emits_lago_binary_and_numeric_params(self):
        study = optuna.create_study(direction="minimize")

        def objective(trial):
            params = build_dnn_search_space(trial)
            binary_keys = [
                "use_price_d_1", "use_price_d_2", "use_price_d_3", "use_price_d_7",
                "use_exog_d", "use_exog_d_1", "use_exog_d_7",
                "use_exog_set_1", "use_exog_set_2",
                "use_dummy",
            ]
            for k in binary_keys:
                assert k in params and params[k] in (0, 1)
            for k in ["n_neurons", "activation", "dropout", "learning_rate",
                      "batch_norm", "preprocessing", "init_method", "l1_reg"]:
                assert k in params
            assert params["n_neurons"] >= 16
            assert 0.0 <= params["dropout"] <= 0.5
            assert params["activation"] in {"relu", "tanh", "elu", "softplus", "sigmoid"}
            assert params["preprocessing"] in {"none", "standard", "asinh"}
            return 0.0

        study.optimize(objective, n_trials=3, show_progress_bar=False)
