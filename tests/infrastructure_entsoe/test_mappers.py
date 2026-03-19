"""Integration tests for ENTSOE XML mapper."""

import pytest

from infrastructure_entsoe.mappers import (
    _parse_energy_prices_xml_to_observation,
    _map_resolution_to_timedelta,
    get_required_text,
)
from domain.curves import Observations

from tests.infrastructure_entsoe.conftest import SAMPLE_ENERGY_PRICES_XML


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
        # Expected: ENTSOE.DE.Daily.EUR
        assert curve_name == "ENTSOE.DE.Daily.EUR"

    def test_source_is_ENTSOE(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        sources = result[0].data_frame["source"].unique().to_list()
        assert sources == ["ENTSOE"]


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
