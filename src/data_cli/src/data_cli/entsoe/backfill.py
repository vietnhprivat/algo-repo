"""ENTSOE backfill commands."""

from datetime import datetime, timezone
from typing import Optional

import typer

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import insert_forecasts_batch, insert_observations_batch
from infrastructure_entsoe.client_factory import create_entsoe_client
from infrastructure_entsoe.entsoe_types import ProcessType

from data_cli.utils import parse_flexible_datetime, resolve_area

backfill_app = typer.Typer()

TOTAL_LOAD_PROCESS_TYPES = {
    "A01": ProcessType.Dayahead,
    "A16": ProcessType.Realised,
    "A31": ProcessType.WeekAhead,
    "A32": ProcessType.MonthAhead,
    "A33": ProcessType.YearAhead,
}


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


@backfill_app.command("total-load")
def backfill_entsoe_total_load(
    area: str = typer.Option(..., "-a", "--area", help="Area tag (e.g., 'DK1', case-insensitive)"),
    process_type: str = typer.Option("A01", "-p", "--processtype", help="Process type code: A01 (Dayahead), A16 (Realised), A31 (WeekAhead), A32 (MonthAhead), A33 (YearAhead)"),
    start: str = typer.Option(..., "-s", "--start", help="Start datetime UTC (flexible formats)"),
    end: Optional[str] = typer.Option(None, "-e", "--end", help="End datetime UTC (flexible formats). Defaults to now."),
) -> None:
    """Backfill ENTSOE total load data (A65) into algo.forecasts."""
    resolved_area = resolve_area(area)
    start_dt = parse_flexible_datetime(start)
    end_dt = parse_flexible_datetime(end) if end is not None else datetime.now(timezone.utc)

    pt_code = process_type.strip().upper()
    if pt_code not in TOTAL_LOAD_PROCESS_TYPES:
        valid = ", ".join(f"{k} ({v.name})" for k, v in TOTAL_LOAD_PROCESS_TYPES.items())
        typer.echo(f"Error: Unknown process type '{process_type}'. Valid types: {valid}")
        raise typer.Exit(code=1)

    pt_enum = TOTAL_LOAD_PROCESS_TYPES[pt_code]

    if start_dt >= end_dt:
        typer.echo(
            f"Error: start ({start_dt.isoformat()}) must be before end ({end_dt.isoformat()})"
        )
        raise typer.Exit(code=1)

    typer.echo(f"Backfilling ENTSOE total load ({pt_enum.name}) for {resolved_area.tag} ({resolved_area.name})")
    typer.echo(f"  From: {start_dt.isoformat()}")
    typer.echo(f"    To: {end_dt.isoformat()}")

    with create_entsoe_client() as entsoe_client:
        forecasts = entsoe_client.fetch_total_load_forecasts(
            area=resolved_area,
            start_date=start_dt,
            end_date=end_dt,
            process_type=pt_code,
            process_type_name=pt_enum.name,
        )

    if not forecasts:
        typer.echo("No data returned from ENTSOE for the given range.")
        raise typer.Exit(code=0)

    total_rows = sum(f.data_frame.height for f in forecasts)
    typer.echo(f"Fetched {len(forecasts)} forecast set(s), {total_rows} total rows.")

    ch_client = create_client()
    try:
        insert_forecasts_batch(ch_client, forecasts)
    finally:
        ch_client.close()

    typer.echo("Successfully inserted into algo.forecasts.")
