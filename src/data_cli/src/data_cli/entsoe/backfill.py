"""ENTSOE backfill commands."""

from datetime import datetime, timezone
from typing import Optional

import typer

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import insert_observations_batch
from infrastructure_entsoe.client_factory import create_entsoe_client

from data_cli.utils import parse_flexible_datetime, resolve_area

backfill_app = typer.Typer()


@backfill_app.command("price-document")
def backfill_entsoe_price_document(
    area: str = typer.Option(..., "-a", "--area", help="Area tag (e.g., 'DK1', case-insensitive)"),
    start: str = typer.Option(..., "-s", "--start", help="Start datetime UTC (flexible formats)"),
    end: Optional[str] = typer.Option(None, "-e", "--end", help="End datetime UTC (flexible formats). Defaults to now."),
) -> None:
    """Backfill ENTSOE price documents (A44) into algo.timeseries."""
    resolved_area = resolve_area(area)
    start_dt = parse_flexible_datetime(start)
    end_dt = parse_flexible_datetime(end) if end is not None else datetime.now(timezone.utc)

    if start_dt >= end_dt:
        typer.echo(
            f"Error: start ({start_dt.isoformat()}) must be before end ({end_dt.isoformat()})"
        )
        raise typer.Exit(code=1)

    typer.echo(f"Backfilling ENTSOE price document for {resolved_area.tag} ({resolved_area.name})")
    typer.echo(f"  From: {start_dt.isoformat()}")
    typer.echo(f"    To: {end_dt.isoformat()}")

    with create_entsoe_client() as entsoe_client:
        observations = entsoe_client.fetch_energy_prices(
            area=resolved_area,
            start_date=start_dt,
            end_date=end_dt,
        )

    if not observations:
        typer.echo("No data returned from ENTSOE for the given range.")
        raise typer.Exit(code=0)

    total_rows = sum(obs.data_frame.height for obs in observations)
    typer.echo(f"Fetched {len(observations)} observation set(s), {total_rows} total rows.")

    ch_client = create_client()
    try:
        insert_observations_batch(ch_client, observations)
    finally:
        ch_client.close()

    typer.echo("Successfully inserted into algo.timeseries.")
