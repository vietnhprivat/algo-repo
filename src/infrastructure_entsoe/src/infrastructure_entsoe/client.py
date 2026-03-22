from datetime import datetime

import httpx
from typing import Literal, Self

from dateutil.relativedelta import relativedelta
from domain.areas import Area
from infrastructure_entsoe.mappers import (
    _parse_energy_prices_xml_to_observation,
    _parse_generation_forecast_xml_to_forecast,
    _parse_total_load_forecast_xml_to_forecast,
    _parse_wind_solar_forecast_xml_to_forecast,
)
from domain.curves import Forecast, Observations
from ratelimit import limits, sleep_and_retry

import zipfile
from io import BytesIO


class EntsoeClientBase:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://web-api.tp.entsoe.eu/api"

    def _handle_energy_prices_response(
        self, content_types_and_contents: list[tuple[str, bytes]]
    ) -> list[Observations]:
        observations: list[Observations] = []
        for content_type, raw_data in content_types_and_contents:
            if "zip" in content_type or raw_data.startswith(b"PK"):
                for xml_file in self._extract_xml_from_zip(raw_data):
                    observations.extend(
                        _parse_energy_prices_xml_to_observation(xml_file)
                    )
            else:
                observations.extend(
                    _parse_energy_prices_xml_to_observation(raw_data)
                )

        return observations

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


    def _build_total_load_forecast_params(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        process_type: str = "A01",
    ):
        params = {
            "documentType": "A65",
            "processType": process_type,
            "outBiddingZone_Domain": area.energy_identification_code,
        }
        params = self._add_start_end_timestamps(params, start_date, end_date)
        params = self._add_api_key(params)
        return params

    def _handle_total_load_forecast_response(
        self, raw_xml_list: list[bytes], process_type_name: str = "Dayahead"
    ) -> list[Forecast]:
        forecasts: list[Forecast] = []
        for raw_data in raw_xml_list:
            forecasts.extend(
                _parse_total_load_forecast_xml_to_forecast(raw_data, process_type_name)
            )
        return forecasts

    def _build_generation_forecast_params(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        process_type: str = "A01",
    ):
        params = {
            "documentType": "A71",
            "processType": process_type,
            "in_Domain": area.energy_identification_code,
        }
        params = self._add_start_end_timestamps(params, start_date, end_date)
        params = self._add_api_key(params)
        return params

    def _handle_generation_forecast_response(
        self, raw_xml_list: list[bytes], process_type_name: str = "Dayahead"
    ) -> list[Forecast]:
        forecasts: list[Forecast] = []
        for raw_data in raw_xml_list:
            forecasts.extend(
                _parse_generation_forecast_xml_to_forecast(raw_data, process_type_name)
            )
        return forecasts

    def _build_wind_solar_forecast_params(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        process_type: str = "A01",
        psr_type: str | None = None,
    ):
        params = {
            "documentType": "A69",
            "processType": process_type,
            "in_Domain": area.energy_identification_code,
        }
        if psr_type is not None:
            params["PsrType"] = psr_type
        params = self._add_start_end_timestamps(params, start_date, end_date)
        params = self._add_api_key(params)
        return params

    def _handle_wind_solar_forecast_response(
        self, raw_xml_list: list[bytes], process_type_name: str = "Dayahead"
    ) -> list[Forecast]:
        forecasts: list[Forecast] = []
        for raw_data in raw_xml_list:
            forecasts.extend(
                _parse_wind_solar_forecast_xml_to_forecast(raw_data, process_type_name)
            )
        return forecasts


class EntsoeClient(EntsoeClientBase):
    def fetch_energy_prices(
        self, area: Area, start_date: datetime, end_date: datetime
    ) -> list[Observations]:
        content_types_and_contents: list[tuple[str, bytes]] = []
        chunk_start = start_date
        while chunk_start < end_date:
            chunk_end = min(chunk_start + relativedelta(months=12), end_date)
            current_offset = 0
            for iteration in range(49):
                if iteration == 48:
                    raise Exception(
                        "Reached maximum number of iterations while fetching energy prices. "
                        "This likely means that there is more data to fetch, but the API is not "
                        "responding with the expected data. Please investigate the issue."
                    )
                params = self._build_energy_prices_params(
                    area, chunk_start, chunk_end, offset=current_offset
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

            chunk_start = chunk_end

        return self._handle_energy_prices_response(content_types_and_contents)

    def fetch_total_load_forecasts(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        process_type: str = "A01",
        process_type_name: str = "Dayahead",
    ) -> list[Forecast]:
        raw_xml_list: list[bytes] = []
        chunk_start = start_date
        while chunk_start < end_date:
            chunk_end = min(chunk_start + relativedelta(months=10), end_date)
            params = self._build_total_load_forecast_params(
                area, chunk_start, chunk_end, process_type=process_type
            )
            response = self._rate_limit_get(self.base_url, params, timeout=30)
            chunk_start = chunk_end

            if response.status_code != 200:
                continue

            raw = response.content
            text = raw.decode("utf-8", errors="ignore")
            if "no matching data found for data item" in text.lower():
                continue

            raw_xml_list.append(raw)

        return self._handle_total_load_forecast_response(raw_xml_list, process_type_name)

    def fetch_generation_forecasts(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        process_type: str = "A01",
        process_type_name: str = "Dayahead",
    ) -> list[Forecast]:
        raw_xml_list: list[bytes] = []
        chunk_start = start_date
        while chunk_start < end_date:
            chunk_end = min(chunk_start + relativedelta(months=10), end_date)
            params = self._build_generation_forecast_params(
                area, chunk_start, chunk_end, process_type=process_type
            )
            response = self._rate_limit_get(self.base_url, params, timeout=30)
            chunk_start = chunk_end

            if response.status_code != 200:
                continue

            raw = response.content
            text = raw.decode("utf-8", errors="ignore")
            if "no matching data found for data item" in text.lower():
                continue

            raw_xml_list.append(raw)

        return self._handle_generation_forecast_response(raw_xml_list, process_type_name)

    def fetch_wind_solar_forecasts(
        self,
        area: Area,
        start_date: datetime,
        end_date: datetime,
        process_type: str = "A01",
        process_type_name: str = "Dayahead",
        psr_type: str | None = None,
    ) -> list[Forecast]:
        raw_xml_list: list[bytes] = []
        chunk_start = start_date
        while chunk_start < end_date:
            chunk_end = min(chunk_start + relativedelta(months=10), end_date)
            params = self._build_wind_solar_forecast_params(
                area, chunk_start, chunk_end, process_type=process_type, psr_type=psr_type
            )
            response = self._rate_limit_get(self.base_url, params, timeout=30)
            chunk_start = chunk_end

            if response.status_code != 200:
                continue

            raw = response.content
            text = raw.decode("utf-8", errors="ignore")
            if "no matching data found for data item" in text.lower():
                continue

            raw_xml_list.append(raw)

        return self._handle_wind_solar_forecast_response(raw_xml_list, process_type_name)

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
