"""Integration tests for ENTSOE client using a fake client (no real API calls)."""

import pytest
from datetime import datetime, timezone

from infrastructure_entsoe.client import EntsoeClientBase
from domain.curves import EnergyPriceObservation
from domain.areas import DE

from tests.infrastructure_entsoe.conftest import SAMPLE_ENERGY_PRICES_XML


class TestEntsoeClientBase:
    """Test EntsoeClientBase using only local logic, no HTTP calls."""

    def setup_method(self):
        self.client = EntsoeClientBase(api_key="fake-api-key-12345")

    def test_api_key_stored(self):
        assert self.client.api_key == "fake-api-key-12345"

    def test_base_url(self):
        assert "entsoe.eu" in self.client.base_url

    def test_build_energy_prices_params(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        params = self.client._build_energy_prices_params(DE, start, end)

        assert params["documentType"] == "A44"
        assert params["in_Domain"] == DE.energy_identification_code
        assert params["out_Domain"] == DE.energy_identification_code
        assert params["securityToken"] == "fake-api-key-12345"
        assert params["periodStart"] == "202401010000"
        assert params["periodEnd"] == "202401020000"

    def test_build_energy_prices_params_with_offset(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        params = self.client._build_energy_prices_params(DE, start, end, offset=200)
        assert params["offset"] == 200

    def test_handle_energy_prices_response_with_xml(self):
        """Feed sample XML through the response handler -> EnergyPriceObservation."""
        content_types_and_contents = [("application/xml", SAMPLE_ENERGY_PRICES_XML)]
        result = self.client._handle_energy_prices_response(content_types_and_contents)
        assert len(result) == 1
        assert isinstance(result[0], EnergyPriceObservation)
        assert result[0].data_frame.shape[0] == 24

    def test_handle_energy_prices_response_multiple_xmls(self):
        """Multiple XML responses are each parsed into an observation."""
        content_types_and_contents = [
            ("application/xml", SAMPLE_ENERGY_PRICES_XML),
            ("application/xml", SAMPLE_ENERGY_PRICES_XML),
        ]
        result = self.client._handle_energy_prices_response(content_types_and_contents)
        assert len(result) == 2

    def test_handle_empty_response_list(self):
        """No response data -> empty list."""
        result = self.client._handle_energy_prices_response([])
        assert result == []


class TestEntsoeClientFactoryValidation:
    """Test that client_factory raises properly without real env vars."""

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
        # Also patch os.getenv to ensure dotenv doesn't provide the value
        original_getenv = __import__("os").getenv
        monkeypatch.setattr("os.getenv", lambda key, *args: None if key == "ENTSOE_API_KEY" else original_getenv(key, *args))
        from infrastructure_entsoe.client_factory import create_entsoe_client

        with pytest.raises(ValueError, match="ENTSOE_API_KEY"):
            create_entsoe_client()

    def test_present_api_key_creates_client(self, monkeypatch):
        monkeypatch.setenv("ENTSOE_API_KEY", "test-key-123")
        from infrastructure_entsoe.client_factory import create_entsoe_client

        client = create_entsoe_client()
        assert client.api_key == "test-key-123"
