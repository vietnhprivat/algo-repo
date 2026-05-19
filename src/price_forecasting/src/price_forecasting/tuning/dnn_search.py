from typing import Any, Dict

import optuna


def build_dnn_search_space(trial: optuna.Trial) -> Dict[str, Any]:
    """Lago §4.3.3 hyperparameter search space.

    10 binary feature-selection HPs:
      - 4 price lags:  use_price_d_1, use_price_d_2, use_price_d_3, use_price_d_7
      - 3 exog lags:   use_exog_d, use_exog_d_1, use_exog_d_7
      - 2 exog sets:   use_exog_set_1, use_exog_set_2
      - 1 calendar:    use_dummy

    Note: the paper §4.3.3 states "11 binary" but the enumerated list totals 10
    distinct suggest_int(0,1) params. The discrepancy arises because some
    descriptions treat use_dummy as covering 2 calendar-feature variants.

    8 architecture HPs (bullets 1–8 of §4.3.3):
      n_neurons, activation, dropout, learning_rate,
      batch_norm, preprocessing, init_method, l1_reg.
    """
    params: Dict[str, Any] = {}
    for k in [
        "use_price_d_1", "use_price_d_2", "use_price_d_3", "use_price_d_7",
        "use_exog_d", "use_exog_d_1", "use_exog_d_7",
        "use_exog_set_1", "use_exog_set_2",
        "use_dummy",
    ]:
        params[k] = trial.suggest_int(k, 0, 1)

    params["n_neurons"] = trial.suggest_int("n_neurons", 16, 512, log=True)
    params["activation"] = trial.suggest_categorical(
        "activation", ["relu", "tanh", "elu", "softplus", "sigmoid"]
    )
    params["dropout"] = trial.suggest_float("dropout", 0.0, 0.5)
    params["learning_rate"] = trial.suggest_float("learning_rate", 1e-5, 1e-1, log=True)
    params["batch_norm"] = trial.suggest_categorical("batch_norm", [False, True])
    params["preprocessing"] = trial.suggest_categorical(
        "preprocessing", ["none", "standard", "asinh"]
    )
    params["init_method"] = trial.suggest_categorical(
        "init_method", ["glorot_uniform", "he_uniform", "lecun_uniform"]
    )
    params["l1_reg"] = trial.suggest_float("l1_reg", 1e-8, 1e-2, log=True)
    return params
