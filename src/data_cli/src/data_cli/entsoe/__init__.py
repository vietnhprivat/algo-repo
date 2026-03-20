import typer

from data_cli.entsoe.backfill import backfill_app

app = typer.Typer(help="ENTSOE data source commands.")
app.add_typer(backfill_app, name="backfill", help="Backfill data from ENTSOE.")
