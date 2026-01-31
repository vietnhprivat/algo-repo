from datetime import datetime, timedelta
from assets.areas import Area
import httpx
from .mappers import _parse_energy_prices_xml_to_observation

import zipfile
from io import BytesIO

class EntsoeClientBase:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://web-api.tp.entsoe.eu/api"


    def _handle_energy_prices_response(self, response: httpx.Response) -> list[dict]:
        response.raise_for_status()
        raw_data = response.content
        content_type = response.headers.get("Content-Type", "").lower()

        all_observations = []
        if "zip" in content_type or raw_data.startswith(b'PK'):
             for xml_file in self._extract_xml_from_zip(raw_data):
                observations = _parse_energy_prices_xml_to_observation(xml_file)
                all_observations.extend(observations)
        else:
            observations = _parse_energy_prices_xml_to_observation(raw_data)
            all_observations.extend(observations)

        return all_observations
    
        
    def _build_energy_prices_params(
            self, 
            area: Area, 
            start_date: datetime, 
            end_date: datetime,
    ):
        params = {
            'documentType': "A44", 
            'out_Domain': area.energy_identification_code,
            'in_Domain': area.energy_identification_code,
        }
        params = self._add_start_end_timestamps(params, start_date, end_date)
        params = self._add_api_key(params)
        return params

    def _add_start_end_timestamps(self, params: dict, start_date: datetime, end_date: datetime) -> dict:
        params_with_timestamps = params.copy()
        params_with_timestamps['periodStart'] = start_date.strftime("%Y%m%d%H%M")
        params_with_timestamps['periodEnd'] = end_date.strftime("%Y%m%d%H%M")
        return params_with_timestamps
    

    def _add_api_key(self, params: dict) -> dict:
        params_with_key = params.copy()
        params_with_key['securityToken'] = self.api_key
        return params_with_key


    def _extract_xml_from_zip(self, zip_data: bytes) -> list[bytes]:
        xml_files = []
        with zipfile.ZipFile(BytesIO(zip_data)) as z:
            for file_info in z.infolist():
                if file_info.filename.endswith('.xml'):
                    with z.open(file_info) as xml_file:
                        xml_files.append(xml_file.read())
        return xml_files    


class EntsoeClient(EntsoeClientBase):
    def fetch_energy_prices(
            self,
            area: Area, 
            start_date: datetime, 
            end_date: datetime
            ):
        params = self._build_energy_prices_params(area, start_date, end_date)
        response = httpx.get(self.base_url, params=params)

        
        return self._handle_energy_prices_response(response)


