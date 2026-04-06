"""Load experiment configs from Python files in the configs/ directory."""

import importlib.util
import sys
from pathlib import Path

import typer

from price_forecasting.configs import ExperimentConfig


def _find_configs_dir() -> Path:
    """Resolve the configs/ directory relative to the repo root (cwd)."""
    return Path.cwd() / "configs"


def load_config(name: str) -> ExperimentConfig:
    """Load configs/{name}.py and return its ``config`` attribute.

    The config file must define a module-level variable ``config``
    of type :class:`ExperimentConfig`.
    """
    configs_dir = _find_configs_dir()
    config_path = configs_dir / f"{name}.py"

    if not configs_dir.exists():
        typer.echo(
            f"Error: Configs directory not found: {configs_dir}\n"
            f"If running in Docker, ensure configs/ is mounted as a volume "
            f"(e.g., -v /path/to/configs:/app/configs)"
        )
        raise typer.Exit(code=1)

    if not config_path.exists():
        available = [f.stem for f in configs_dir.glob("*.py") if f.stem != "__init__"]
        typer.echo(
            f"Error: Config file not found: {config_path}\n"
            f"Available configs: {', '.join(sorted(available)) or '(none)'}"
        )
        raise typer.Exit(code=1)

    module_name = f"configs.{name}"
    spec = importlib.util.spec_from_file_location(module_name, config_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        typer.echo(f"Error: Failed to load config '{name}': {e}")
        raise typer.Exit(code=1)

    if not hasattr(module, "config"):
        typer.echo(
            f"Error: Config file '{name}.py' must define a 'config' variable.\n"
            f"Example: config = ExperimentConfig(...)"
        )
        raise typer.Exit(code=1)

    config = module.config
    if not isinstance(config, ExperimentConfig):
        typer.echo(
            f"Error: 'config' in '{name}.py' must be an ExperimentConfig, "
            f"got {type(config).__name__}"
        )
        raise typer.Exit(code=1)

    return config
