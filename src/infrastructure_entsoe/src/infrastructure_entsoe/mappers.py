
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import polars as pl

from domain.areas import get_area_from_energy_code
from domain.curves import EnergyPriceObservation
from infrastructure_entsoe.entsoe_types import (
    MarketAgreementType,
    BusinessType,
    AuctionType,
    DocumentType,
)


def get_required_text(element: ET.Element, tag: str, ns: dict) -> str:
    found = element.find(tag, ns)
    if found is None or found.text is None:
        raise ValueError(f"Missing required XML element or text: {tag}")
    return found.text


def _parse_energy_prices_xml_to_observation(xml_data: bytes) -> EnergyPriceObservation:
    root = ET.fromstring(xml_data)
    ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}
    doc_type = get_required_text(root, "ns:type", ns)

    final_observations: list[pl.DataFrame] = []
    for timeseries in root.findall("ns:TimeSeries", ns):
        in_area = get_area_from_energy_code(
            get_required_text(timeseries, "ns:in_Domain.mRID", ns)
        )
        out_area = get_area_from_energy_code(
            get_required_text(timeseries, "ns:out_Domain.mRID", ns)
        )
        base_data = {
            "doc_type": DocumentType(doc_type).name,
            "mrid": get_required_text(timeseries, "ns:mRID", ns),
            "in_Domain.mRID": in_area.tag,
            "out_Domain.mRID": out_area.tag,
            "auction_type": AuctionType(get_required_text(timeseries, "ns:auction.type", ns)).name,
            "business_type": BusinessType(get_required_text(timeseries, "ns:businessType", ns)).name,
            "contract_type": MarketAgreementType(get_required_text(timeseries, "ns:contract_MarketAgreement.type", ns)).name,
            "curve_type": get_required_text(timeseries, "ns:curveType", ns),
            "currency": get_required_text(timeseries, "ns:currency_Unit.name", ns),
            "unit": get_required_text(timeseries, "ns:price_Measure_Unit.name", ns),
        }

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
                    "start_utc": pl.datetime_range(
                        start=start_utc,
                        end=end_utc - delta,
                        interval=delta,
                        eager=True,
                    )
                }
            )
            start_timestamps_df = pl.DataFrame(
                {"start_utc": all_start_timestamps, "price": all_prices}
            )
            merged_df = start_entries.join(
                start_timestamps_df, on="start_utc", how="left"
            )
            merged_df = merged_df.with_columns(pl.col("price").forward_fill())
            merged_df = merged_df.sort("start_utc")
            merged_df = merged_df.with_columns(
                (pl.col("start_utc") + delta).alias("end_utc")
            )

            ingestion_ts = datetime.now(timezone.utc)
            merged_df = merged_df.with_columns(
                source=pl.lit("ENTSOE"),
                area=pl.lit(in_area.tag),
                area_timezone=pl.lit(in_area.timezone.key),
                auction_type=pl.lit(base_data["auction_type"]),
                business_type=pl.lit(base_data["business_type"]),
                contract_type=pl.lit(base_data["contract_type"]),
                currency=pl.lit(base_data["currency"]),
                ingestion_timestamp=pl.lit(ingestion_ts),
            )
            final_observations.append(merged_df)

    polars_df = pl.concat(final_observations)
    polars_df = polars_df.select(list(EnergyPriceObservation.SCHEMA.keys()))

    return EnergyPriceObservation(polars_df)


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


def save_raw_xml_to_file(xml_data: bytes, file_path: str) -> None:
    with open(file_path, "wb") as file:
        file.write(xml_data)
