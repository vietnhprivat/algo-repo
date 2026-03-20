"""Data CLI entry point."""

import typer

from data_cli.entsoe import app as entsoe_app

app = typer.Typer(help="CLI tool for backfilling historical data into ClickHouse.")

app.add_typer(entsoe_app, name="entsoe")


if __name__ == "__main__":
    app()
