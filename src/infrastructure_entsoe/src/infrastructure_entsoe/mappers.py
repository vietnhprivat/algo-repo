import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd
from infrastructure_entsoe.types import (
    MarketAgreementType,
    BusinessType,
    AuctionType,
    DocumentType,
)


def _parse_energy_prices_xml_to_observation(xml_data: bytes) -> list[dict]:
    root = ET.fromstring(xml_data)
    ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}

    final_observations = []

    doc_type = root.find("ns:type", ns).text

    for timeseries in root.findall("ns:TimeSeries", ns):
        base_data = {
            "doc_type": DocumentType(doc_type).name,
            "mrid": timeseries.find("ns:mRID", ns).text,
            "auction_type": AuctionType(
                timeseries.find("ns:auction.type", ns).text
            ).name,
            "business_type": BusinessType(
                timeseries.find("ns:businessType", ns).text
            ).name,
            "contract_type": MarketAgreementType(
                timeseries.find("ns:contract_MarketAgreement.type", ns).text
            ).name,
            "curve_type": timeseries.find("ns:curveType", ns).text,
            "currency": timeseries.find("ns:currency_Unit.name", ns).text,
            "unit": timeseries.find("ns:price_Measure_Unit.name", ns).text,
        }

        for period in timeseries.findall("ns:Period", ns):
            resolution = period.find("ns:resolution", ns).text
            delta = _map_resolution_to_timedelta(resolution)
            start_raw = period.find("ns:timeInterval/ns:start", ns).text
            end_raw = period.find("ns:timeInterval/ns:end", ns).text
            start_utc = datetime.fromisoformat(start_raw)
            end_utc = datetime.fromisoformat(end_raw)

            all_prices = []
            all_positions = []
            for point in period.findall("ns:Point", ns):
                position = int(point.find("ns:position", ns).text)
                price = float(point.find("ns:price.amount", ns).text)
                all_positions.append(position)
                all_prices.append(price)

            data_range = pd.date_range(start=start_utc, end=end_utc - delta, freq=delta)
            all_start_entries = pd.DataFrame({"start_utc": data_range})
            all_start_timestamps = _map_A03_curve(start_utc, delta, all_positions)
            all_start_timestamps_df = pd.DataFrame(
                {"start_utc": all_start_timestamps, "price": all_prices}
            )
            merged_df = pd.merge(
                all_start_entries, all_start_timestamps_df, on="start_utc", how="left"
            ).ffill()
            merged_df = merged_df.sort_values(by="start_utc").reset_index(drop=True)
            merged_df["end_utc"] = merged_df["start_utc"] + delta
            final_observations.append(merged_df)

    result_df = pd.concat(final_observations, axis=0)
    result_df["auction_type"] = base_data["auction_type"]
    result_df["business_type"] = base_data["business_type"]
    result_df["contract_type"] = base_data["contract_type"]
    result_df.index.name = "position"

    return result_df


def _map_A03_curve(start_utc: datetime, delta: str, positions: list[int]) -> list[dict]:
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
