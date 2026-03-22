"""Tests for forecast_cli config_loader."""

import pytest
from click.exceptions import Exit

from price_forecasting import ExperimentConfig


class TestConfigLoader:

    def test_load_valid_config(self, tmp_path):
        """Loading a valid config file returns an ExperimentConfig."""
        from unittest.mock import patch
        from forecast_cli.config_loader import load_config

        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "test_config.py"
        config_file.write_text(
            "from price_forecasting import ExperimentConfig\n"
            "config = ExperimentConfig(\n"
            "    experiment_name='test',\n"
            "    results_dir='results',\n"
            "    area='DE',\n"
            ")\n"
        )

        with patch("forecast_cli.config_loader._find_configs_dir", return_value=config_dir):
            result = load_config("test_config")

        assert isinstance(result, ExperimentConfig)
        assert result.experiment_name == "test"
        assert result.area == "DE"

    def test_load_missing_config_exits(self, tmp_path):
        """Loading a non-existent config exits with code 1."""
        from unittest.mock import patch
        from forecast_cli.config_loader import load_config

        config_dir = tmp_path / "configs"
        config_dir.mkdir()

        with patch("forecast_cli.config_loader._find_configs_dir", return_value=config_dir):
            with pytest.raises(Exit):
                load_config("nonexistent")

    def test_load_config_missing_attr_exits(self, tmp_path):
        """Config file without 'config' variable exits with code 1."""
        from unittest.mock import patch
        from forecast_cli.config_loader import load_config

        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "bad_config.py"
        config_file.write_text("x = 42\n")

        with patch("forecast_cli.config_loader._find_configs_dir", return_value=config_dir):
            with pytest.raises(Exit):
                load_config("bad_config")

    def test_load_config_wrong_type_exits(self, tmp_path):
        """Config file with wrong type for 'config' exits with code 1."""
        from unittest.mock import patch
        from forecast_cli.config_loader import load_config

        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "wrong_type.py"
        config_file.write_text("config = 'not an ExperimentConfig'\n")

        with patch("forecast_cli.config_loader._find_configs_dir", return_value=config_dir):
            with pytest.raises(Exit):
                load_config("wrong_type")
