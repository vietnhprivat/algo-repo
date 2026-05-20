from typing import Any, Dict

import optuna


def build_dnn_search_space(trial: optuna.Trial) -> Dict[str, Any]:
    """DNN architecture search space (Lago §4.3.3, architecture HPs only).

    Returns the 6 architecture HPs that the objective actually exercises:
      n_neurons, activation, dropout, learning_rate, batch_norm, l1_reg.

    Lago §4.3.3 also lists 10 binary feature/selector HPs and `preprocessing`/
    `init_method` choices. Those are intentionally omitted here until the
    preprocessor and model expose constructor-level toggles; until then,
    suggesting them would create inert search dimensions that waste trials.
    """
    params: Dict[str, Any] = {}
    params["n_neurons"] = trial.suggest_int("n_neurons", 16, 512, log=True)
    params["activation"] = trial.suggest_categorical(
        "activation", ["relu", "tanh", "elu", "softplus", "sigmoid"]
    )
    params["dropout"] = trial.suggest_float("dropout", 0.0, 0.5)
    params["learning_rate"] = trial.suggest_float("learning_rate", 1e-5, 1e-1, log=True)
    params["batch_norm"] = trial.suggest_categorical("batch_norm", [False, True])
    params["l1_reg"] = trial.suggest_float("l1_reg", 1e-8, 1e-2, log=True)
    return params
