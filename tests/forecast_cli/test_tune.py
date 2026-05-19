from typer.testing import CliRunner

from forecast_cli.main import app


class TestTuneCommand:
    def test_dry_run_short_circuits(self):
        runner = CliRunner()
        # dk1_lear has val_start_date / val_end_date set (Task P1.3).
        result = runner.invoke(app, ["tune", "dk1_lear", "--n-trials", "1", "--dry-run"])
        assert result.exit_code == 0, result.stdout
        assert "study_name=dk1_lear-" in result.stdout
        assert "n_trials=1" in result.stdout
