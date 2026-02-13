from datetime import datetime

import httpx
from typing import Literal, Self

from domain.areas import Area
from infrastructure_entsoe.mappers import _parse_energy_prices_xml_to_observation
from domain.curves import EnergyPriceObservation
from ratelimit import limits, sleep_and_retry

import zipfile
from io import BytesIO


class EntsoeClientBase:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://web-api.tp.entsoe.eu/api"

    def _handle_energy_prices_response(
        self, content_types_and_contents: list[tuple[str, bytes]]
    ) -> list[EnergyPriceObservation]:
        energy_price_observations: list[EnergyPriceObservation] = []
        for content_type, raw_data in content_types_and_contents:
            if "zip" in content_type or raw_data.startswith(b"PK"):
                for xml_file in self._extract_xml_from_zip(raw_data):
                    energy_price_observations.append(
                        _parse_energy_prices_xml_to_observation(xml_file)
                    )
            else:
                energy_price_observations.append(
                    _parse_energy_prices_xml_to_observation(raw_data)
                )

        return energy_price_observations

    def _build_energy_prices_params(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        offset: int = 0,
    ):
        params = {
            "documentType": "A44",
            "out_Domain": area.energy_identification_code,
            "in_Domain": area.energy_identification_code,
            "offset": offset,
        }
        params = self._add_start_end_timestamps(params, start_date, end_date)
        params = self._add_api_key(params)
        return params

    def _add_start_end_timestamps(
        self, params: dict, start_date: datetime, end_date: datetime
    ) -> dict:
        params_with_timestamps = params.copy()
        params_with_timestamps["periodStart"] = start_date.strftime("%Y%m%d%H%M")
        params_with_timestamps["periodEnd"] = end_date.strftime("%Y%m%d%H%M")
        return params_with_timestamps

    def _add_api_key(self, params: dict) -> dict:
        params_with_key = params.copy()
        params_with_key["securityToken"] = self.api_key
        return params_with_key

    def _extract_xml_from_zip(self, zip_data: bytes) -> list[bytes]:
        xml_files = []
        with zipfile.ZipFile(BytesIO(zip_data)) as z:
            for file_info in z.infolist():
                if file_info.filename.endswith(".xml"):
                    with z.open(file_info) as xml_file:
                        xml_files.append(xml_file.read())
        return xml_files


class EntsoeClient(EntsoeClientBase):
    def fetch_energy_prices(
        self, area: Area, start_date: datetime, end_date: datetime
    ) -> list[EnergyPriceObservation]:
        content_types_and_contents: list[tuple[str, bytes]] = []
        current_offset = 0
        for iteration in range(49):
            if iteration == 48:
                raise Exception(
                    "Reached maximum number of iterations while fetching energy prices. This likely means that there is more data to fetch, but the API is not responding with the expected data. Please investigate the issue."
                )
            params = self._build_energy_prices_params(
                area, start_date, end_date, offset=current_offset
            )
            response = self._rate_limit_get(self.base_url, params, timeout=30)
            current_offset += 100

            if response.status_code != 200:
                continue

            raw = response.content
            text = raw.decode("utf-8", errors="ignore")
            if "no matching data found for data item" in text.lower():
                break

            content_type = response.headers.get("Content-Type", "").lower()
            content_types_and_contents.append((content_type, raw))

        return self._handle_energy_prices_response(content_types_and_contents)

    @sleep_and_retry
    @limits(calls=400, period=60)
    def _rate_limit_get(
        self, base_url: str, params: dict, timeout: int = 30
    ) -> httpx.Response:
        return httpx.get(base_url, params=params, timeout=timeout)

    def __enter__(self) -> Self:
        self.client = httpx.Client()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> Literal[False]:
        if self.client is None:
            return False

        self.client.close()
        self.client = None
        return False
