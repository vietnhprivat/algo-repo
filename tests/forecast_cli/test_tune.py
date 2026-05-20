from typer.testing import CliRunner

from forecast_cli.main import app


class TestTuneCommand:
    def test_dry_run_short_circuits(self):
        runner = CliRunner()
        # dk1_dnn has model_type='dnn' plus val_start_date / val_end_date set.
        result = runner.invoke(app, ["tune", "dk1_dnn", "--n-trials", "1", "--dry-run"])
        assert result.exit_code == 0, result.stdout
        assert "study_name=dk1_dnn-" in result.stdout
        assert "n_trials=1" in result.stdout

    def test_rejects_non_dnn_config(self):
        # dk1_lear has model_type='lear', so tune must refuse it.
        runner = CliRunner()
        result = runner.invoke(app, ["tune", "dk1_lear", "--n-trials", "1", "--dry-run"])
        assert result.exit_code != 0
