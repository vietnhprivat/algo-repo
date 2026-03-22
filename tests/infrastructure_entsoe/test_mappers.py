"""Integration tests for ENTSOE XML mapper."""

import pytest
from datetime import datetime, timezone

from infrastructure_entsoe.mappers import (
    _parse_energy_prices_xml_to_observation,
    _parse_generation_forecast_xml_to_forecast,
    _parse_total_load_forecast_xml_to_forecast,
    _parse_wind_solar_forecast_xml_to_forecast,
    _map_resolution_to_timedelta,
    get_required_text,
)
from domain.curves import Forecast, Observations

from tests.infrastructure_entsoe.conftest import (
    SAMPLE_ENERGY_PRICES_XML,
    SAMPLE_GENERATION_FORECAST_XML,
    SAMPLE_TOTAL_LOAD_FORECAST_XML,
    SAMPLE_WIND_SOLAR_FORECAST_XML,
)


class TestParseEnergyPricesXml:
    """Test the full XML -> list[Observations] pipeline with sample data."""

    def test_returns_list_of_observations(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Observations)

    def test_correct_number_of_rows(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        # 24 hours in the sample data
        assert result[0].data_frame.shape[0] == 24

    def test_output_schema_matches(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        expected_columns = list(Observations.SCHEMA.keys())
        assert list(result[0].data_frame.columns) == expected_columns

    def test_area_is_DE(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        areas = result[0].data_frame["area"].unique().to_list()
        assert areas == ["DE"]

    def test_values_are_positive_floats(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        values = result[0].data_frame["value"].to_list()
        assert all(isinstance(v, float) for v in values)
        assert all(v > 0 for v in values)

    def test_timestamps_are_utc(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        first_ts = result[0].data_frame["timestamp_utc"][0]
        assert first_ts.tzinfo is not None

    def test_curve_name_contains_currency(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        curve_name = result[0].curve_name
        assert "EUR" in curve_name

    def test_curve_name_format(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        curve_name = result[0].curve_name
        # Expected: ENTSOE DE EnergyPrice Daily EUR
        assert curve_name == "ENTSOE DE EnergyPrice Daily EUR"

    def test_source_is_ENTSOE(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        sources = result[0].data_frame["source"].unique().to_list()
        assert sources == ["ENTSOE"]


class TestParseTotalLoadForecastXml:
    """Test the full XML -> list[Forecast] pipeline with sample data."""

    def test_returns_list_of_forecasts(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Forecast)

    def test_correct_number_of_rows(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        assert result[0].data_frame.shape[0] == 24

    def test_output_schema_matches(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        expected_columns = list(Forecast.SCHEMA.keys())
        assert list(result[0].data_frame.columns) == expected_columns

    def test_area_is_DE(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        areas = result[0].data_frame["area"].unique().to_list()
        assert areas == ["DE"]

    def test_values_are_positive_floats(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        values = result[0].data_frame["value"].to_list()
        assert all(isinstance(v, float) for v in values)
        assert all(v > 0 for v in values)

    def test_timestamps_are_utc(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        first_ts = result[0].data_frame["timestamp_utc"][0]
        assert first_ts.tzinfo is not None

    def test_curve_name_format(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        assert result[0].curve_name == "ENTSOE DE TotalLoad Dayahead"

    def test_source_is_ENTSOE(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        sources = result[0].data_frame["source"].unique().to_list()
        assert sources == ["ENTSOE"]

    def test_model_is_ENTSOE(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        models = result[0].data_frame["model"].unique().to_list()
        assert models == ["ENTSOE"]

    def test_issued_utc_matches_created_datetime(self):
        result = _parse_total_load_forecast_xml_to_forecast(SAMPLE_TOTAL_LOAD_FORECAST_XML)
        issued = result[0].data_frame["issued_utc"][0]
        expected = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        assert issued == expected

class TestParseGenerationForecastXml:
    """Test the full XML -> list[Forecast] pipeline for generation forecast."""

    def test_returns_list_of_forecasts(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Forecast)

    def test_correct_number_of_rows(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        assert result[0].data_frame.shape[0] == 24

    def test_output_schema_matches(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        expected_columns = list(Forecast.SCHEMA.keys())
        assert list(result[0].data_frame.columns) == expected_columns

    def test_area_is_DE(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        areas = result[0].data_frame["area"].unique().to_list()
        assert areas == ["DE"]

    def test_curve_name_format(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        assert result[0].curve_name == "ENTSOE DE Generation Dayahead"

    def test_source_is_ENTSOE(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        sources = result[0].data_frame["source"].unique().to_list()
        assert sources == ["ENTSOE"]

    def test_model_is_ENTSOE(self):
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        models = result[0].data_frame["model"].unique().to_list()
        assert models == ["ENTSOE"]

    def test_resolves_inBiddingZone_domain(self):
        """Generation XML uses inBiddingZone_Domain.mRID, not outBiddingZone."""
        result = _parse_generation_forecast_xml_to_forecast(SAMPLE_GENERATION_FORECAST_XML)
        assert result[0].data_frame["area"][0] == "DE"


class TestParseWindSolarForecastXml:
    """Test the full XML -> list[Forecast] pipeline for wind/solar forecast."""

    def test_returns_two_forecasts(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(f, Forecast) for f in result)

    def test_correct_number_of_rows_with_forward_fill(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        for f in result:
            assert f.data_frame.shape[0] == 24

    def test_output_schema_matches(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        expected_columns = list(Forecast.SCHEMA.keys())
        for f in result:
            assert list(f.data_frame.columns) == expected_columns

    def test_curve_names_contain_psr_types(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        curve_names = sorted(f.curve_name for f in result)
        assert curve_names == ["ENTSOE BE Solar Dayahead", "ENTSOE BE WindOnshore Dayahead"]

    def test_area_is_BE(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        for f in result:
            areas = f.data_frame["area"].unique().to_list()
            assert areas == ["BE"]

    def test_source_is_ENTSOE(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        for f in result:
            sources = f.data_frame["source"].unique().to_list()
            assert sources == ["ENTSOE"]

    def test_model_is_ENTSOE(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        for f in result:
            models = f.data_frame["model"].unique().to_list()
            assert models == ["ENTSOE"]

    def test_solar_forward_fill_gaps(self):
        """Solar has gaps at positions 2-6; forward-fill should set them to 0 (value at position 1)."""
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        solar = [f for f in result if "Solar" in f.curve_name][0]
        values = solar.data_frame["value"].to_list()
        # Positions 2-6 should be forward-filled with 0.0 (from position 1)
        assert values[1] == 0.0  # position 2
        assert values[5] == 0.0  # position 6

    def test_issued_utc_matches_created_datetime(self):
        result = _parse_wind_solar_forecast_xml_to_forecast(SAMPLE_WIND_SOLAR_FORECAST_XML)
        from datetime import datetime, timezone
        expected = datetime(2023, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        for f in result:
            assert f.data_frame["issued_utc"][0] == expected


class TestMapResolutionToTimedelta:
    def test_pt60m(self):
        from datetime import timedelta
        assert _map_resolution_to_timedelta("PT60M") == timedelta(hours=1)

    def test_pt15m(self):
        from datetime import timedelta
        assert _map_resolution_to_timedelta("PT15M") == timedelta(minutes=15)

    def test_pt30m(self):
        from datetime import timedelta
        assert _map_resolution_to_timedelta("PT30M") == timedelta(minutes=30)

    def test_unknown_defaults_to_hourly(self):
        from datetime import timedelta
        assert _map_resolution_to_timedelta("PT5M") == timedelta(hours=1)


class TestGetRequiredText:
    def test_raises_on_missing_element(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring("<root><child>text</child></root>")
        with pytest.raises(ValueError, match="Missing required XML element"):
            get_required_text(root, "nonexistent", {})

    def test_returns_text_for_existing_element(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring("<root><child>hello</child></root>")
        assert get_required_text(root, "child", {}) == "hello"


class TestXmlParsingWithMalformedData:
    def test_missing_type_element_raises(self):
        xml = b"""\
        <Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
            <mRID>Doc001</mRID>
            <TimeSeries>
                <mRID>TS001</mRID>
            </TimeSeries>
        </Publication_MarketDocument>
        """
        with pytest.raises(ValueError, match="Missing required XML element"):
            _parse_energy_prices_xml_to_observation(xml)
