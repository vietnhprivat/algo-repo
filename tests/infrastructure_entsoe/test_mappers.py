"""Integration tests for ENTSOE XML mapper."""

import pytest
from datetime import datetime, timezone

from infrastructure_entsoe.mappers import (
    _parse_energy_prices_xml_to_observation,
    _map_resolution_to_timedelta,
    get_required_text,
)
from assets.data_objects import EnergyPriceObservation

from tests.infrastructure_entsoe.conftest import SAMPLE_ENERGY_PRICES_XML


class TestParseEnergyPricesXml:
    """Test the full XML -> EnergyPriceObservation pipeline with sample data."""

    def test_returns_energy_price_observation(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        assert isinstance(result, EnergyPriceObservation)

    def test_correct_number_of_rows(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        # 24 hours in the sample data
        assert result.data_frame.shape[0] == 24

    def test_output_schema_matches(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        expected_columns = list(EnergyPriceObservation.SCHEMA.keys())
        assert list(result.data_frame.columns) == expected_columns

    def test_area_is_DE(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        areas = result.data_frame["area"].unique().to_list()
        assert areas == ["DE"]

    def test_prices_are_positive_floats(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        prices = result.data_frame["price"].to_list()
        assert all(isinstance(p, float) for p in prices)
        assert all(p > 0 for p in prices)

    def test_start_utc_is_before_end_utc(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        df = result.data_frame
        starts = df["start_utc"].to_list()
        ends = df["end_utc"].to_list()
        for s, e in zip(starts, ends):
            assert s < e

    def test_timestamps_are_utc(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        first_start = result.data_frame["start_utc"][0]
        assert first_start.tzinfo is not None

    def test_currency_is_EUR(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        currencies = result.data_frame["currency"].unique().to_list()
        assert currencies == ["EUR"]

    def test_source_is_ENTSOE(self):
        result = _parse_energy_prices_xml_to_observation(SAMPLE_ENERGY_PRICES_XML)
        sources = result.data_frame["source"].unique().to_list()
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
        </Publication_MarketDocument>
        """
        with pytest.raises(ValueError, match="Missing required XML element"):
            _parse_energy_prices_xml_to_observation(xml)
