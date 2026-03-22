
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import polars as pl

from domain.areas import get_area_from_energy_code
from domain.curves import Forecast, Observations
from infrastructure_entsoe.entsoe_types import (
    MarketAgreementType,
)

WIND_SOLAR_PSR_NAMES = {
    "B16": "Solar",
    "B18": "WindOffshore",
    "B19": "WindOnshore",
}


def get_required_text(element: ET.Element, tag: str, ns: dict) -> str:
    found = element.find(tag, ns)
    if found is None or found.text is None:
        raise ValueError(f"Missing required XML element or text: {tag}")
    return found.text


def _parse_energy_prices_xml_to_observation(xml_data: bytes) -> list[Observations]:
    root = ET.fromstring(xml_data)
    ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}

    # Group rows by curve_name so we can return one Observations per curve
    curves: dict[str, list[pl.DataFrame]] = {}

    for timeseries in root.findall("ns:TimeSeries", ns):
        in_area = get_area_from_energy_code(
            get_required_text(timeseries, "ns:in_Domain.mRID", ns)
        )

        contract_type = MarketAgreementType(get_required_text(timeseries, "ns:contract_MarketAgreement.type", ns)).name
        currency = get_required_text(timeseries, "ns:currency_Unit.name", ns)
        curve_name = f"ENTSOE {in_area.tag} EnergyPrice {contract_type} {currency}"

        for period in timeseries.findall("ns:Period", ns):
            resolution = get_required_text(period, "ns:resolution", ns)
            delta = _map_resolution_to_timedelta(resolution)
            start_raw = get_required_text(period, "ns:timeInterval/ns:start", ns)
            end_raw = get_required_text(period, "ns:timeInterval/ns:end", ns)
            start_utc = datetime.fromisoformat(start_raw).astimezone(timezone.utc)
            end_utc = datetime.fromisoformat(end_raw).astimezone(timezone.utc)

            all_prices: list[float] = []
            all_positions: list[int] = []
            for point in period.findall("ns:Point", ns):
                position = int(get_required_text(point, "ns:position", ns))
                price = float(get_required_text(point, "ns:price.amount", ns))
                all_positions.append(position)
                all_prices.append(price)

            all_start_timestamps = _map_A03_curve(start_utc, delta, all_positions)
            start_entries = pl.DataFrame(
                {
                    "timestamp_utc": pl.datetime_range(
                        start=start_utc,
                        end=end_utc - delta,
                        interval=delta,
                        eager=True,
                    )
                }
            )
            start_timestamps_df = pl.DataFrame(
                {"timestamp_utc": all_start_timestamps, "value": all_prices}
            )
            merged_df = start_entries.join(
                start_timestamps_df, on="timestamp_utc", how="left"
            )
            merged_df = merged_df.with_columns(pl.col("value").forward_fill())
            merged_df = merged_df.sort("timestamp_utc")

            ingestion_ts = datetime.now(timezone.utc)
            merged_df = merged_df.with_columns(
                source=pl.lit("ENTSOE"),
                curve_name=pl.lit(curve_name),
                area=pl.lit(in_area.tag),
                timezone=pl.lit(in_area.timezone.key),
                value=pl.col("value").cast(pl.Float32),
                ingested_utc=pl.lit(ingestion_ts),
            )
            merged_df = merged_df.select(list(Observations.SCHEMA.keys()))
            curves.setdefault(curve_name, []).append(merged_df)

    return [
        Observations(curve_name, pl.concat(frames))
        for curve_name, frames in curves.items()
    ]


def _map_A03_curve(start_utc: datetime, delta: timedelta, positions: list[int]) -> list[dict]:
    all_time_step_start = []
    for point in positions:
        time_step_start = start_utc + (point - 1) * delta
        all_time_step_start.append(time_step_start)

    return all_time_step_start


def _map_resolution_to_timedelta(resolution: str) -> timedelta:
    return {
        "PT15M": timedelta(minutes=15),
        "PT30M": timedelta(minutes=30),
        "PT60M": timedelta(hours=1),
    }.get(resolution, timedelta(hours=1))


def _resolve_bidding_zone_domain(timeseries: ET.Element, ns: dict) -> str:
    for field in ["ns:outBiddingZone_Domain.mRID", "ns:inBiddingZone_Domain.mRID"]:
        found = timeseries.find(field, ns)
        if found is not None and found.text is not None:
            return found.text
    raise ValueError("Missing required XML element: outBiddingZone_Domain.mRID or inBiddingZone_Domain.mRID")


def _parse_gl_market_document_xml_to_forecast(
    xml_data: bytes, curve_type: str | None, process_type_name: str = "Dayahead"
) -> list[Forecast]:
    root = ET.fromstring(xml_data)
    ns = {"ns": "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"}

    created_raw = get_required_text(root, "ns:createdDateTime", ns)
    issued_utc = datetime.fromisoformat(created_raw).astimezone(timezone.utc)

    curves: dict[str, list[pl.DataFrame]] = {}

    for timeseries in root.findall("ns:TimeSeries", ns):
        area = get_area_from_energy_code(
            _resolve_bidding_zone_domain(timeseries, ns)
        )

        if curve_type is not None:
            ct = curve_type
        else:
            psr_el = timeseries.find("ns:MktPSRType/ns:psrType", ns)
            if psr_el is not None and psr_el.text is not None:
                ct = WIND_SOLAR_PSR_NAMES.get(psr_el.text, psr_el.text)
            else:
                raise ValueError("Missing required XML element: MktPSRType/psrType")

        curve_name = f"ENTSOE {area.tag} {ct} {process_type_name}"

        for period in timeseries.findall("ns:Period", ns):
            resolution = get_required_text(period, "ns:resolution", ns)
            delta = _map_resolution_to_timedelta(resolution)
            start_raw = get_required_text(period, "ns:timeInterval/ns:start", ns)
            end_raw = get_required_text(period, "ns:timeInterval/ns:end", ns)
            start_utc = datetime.fromisoformat(start_raw).astimezone(timezone.utc)
            end_utc = datetime.fromisoformat(end_raw).astimezone(timezone.utc)

            all_quantities: list[float] = []
            all_positions: list[int] = []
            for point in period.findall("ns:Point", ns):
                position = int(get_required_text(point, "ns:position", ns))
                quantity = float(get_required_text(point, "ns:quantity", ns))
                all_positions.append(position)
                all_quantities.append(quantity)

            all_start_timestamps = _map_A03_curve(start_utc, delta, all_positions)
            start_entries = pl.DataFrame(
                {
                    "timestamp_utc": pl.datetime_range(
                        start=start_utc,
                        end=end_utc - delta,
                        interval=delta,
                        eager=True,
                    )
                }
            )
            start_timestamps_df = pl.DataFrame(
                {"timestamp_utc": all_start_timestamps, "value": all_quantities}
            )
            merged_df = start_entries.join(
                start_timestamps_df, on="timestamp_utc", how="left"
            )
            merged_df = merged_df.with_columns(pl.col("value").forward_fill())
            merged_df = merged_df.sort("timestamp_utc")

            ingestion_ts = datetime.now(timezone.utc)
            merged_df = merged_df.with_columns(
                source=pl.lit("ENTSOE"),
                curve_name=pl.lit(curve_name),
                area=pl.lit(area.tag),
                area_timezone=pl.lit(area.timezone.key),
                model=pl.lit("ENTSOE"),
                issued_utc=pl.lit(issued_utc),
                issued_timezone=pl.lit(area.timezone.key),
                value=pl.col("value").cast(pl.Float32),
                ingested_utc=pl.lit(ingestion_ts),
            )
            merged_df = merged_df.select(list(Forecast.SCHEMA.keys()))
            curves.setdefault(curve_name, []).append(merged_df)

    return [
        Forecast(curve_name, pl.concat(frames))
        for curve_name, frames in curves.items()
    ]


def _parse_total_load_forecast_xml_to_forecast(
    xml_data: bytes, process_type_name: str = "Dayahead"
) -> list[Forecast]:
    return _parse_gl_market_document_xml_to_forecast(xml_data, "TotalLoad", process_type_name)


def _parse_generation_forecast_xml_to_forecast(
    xml_data: bytes, process_type_name: str = "Dayahead"
) -> list[Forecast]:
    return _parse_gl_market_document_xml_to_forecast(xml_data, "Generation", process_type_name)


def _parse_wind_solar_forecast_xml_to_forecast(
    xml_data: bytes, process_type_name: str = "Dayahead"
) -> list[Forecast]:
    return _parse_gl_market_document_xml_to_forecast(xml_data, None, process_type_name)


def save_raw_xml_to_file(xml_data: bytes, file_path: str) -> None:
    with open(file_path, "wb") as file:
        file.write(xml_data)
