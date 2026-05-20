import optuna

from price_forecasting.tuning.dnn_search import build_dnn_search_space


class TestDnnSearchSpace:
    def test_emits_architecture_params(self):
        study = optuna.create_study(direction="minimize")

        def objective(trial):
            params = build_dnn_search_space(trial)
            architecture_keys = [
                "n_neurons", "activation", "dropout", "learning_rate",
                "batch_norm", "l1_reg",
            ]
            assert set(params) == set(architecture_keys)
            assert params["n_neurons"] >= 16
            assert 0.0 <= params["dropout"] <= 0.5
            assert params["activation"] in {"relu", "tanh", "elu", "softplus", "sigmoid"}
            assert isinstance(params["batch_norm"], bool)
            return 0.0

        study.optimize(objective, n_trials=3, show_progress_bar=False)
