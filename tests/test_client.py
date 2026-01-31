from datetime import datetime, timedelta
from io import BytesIO
import zipfile

import httpx

from assets.areas import DK1
from infrastructure_entsoe.client import EntsoeClientBase, EntsoeClient
import infrastructure_entsoe.client as client_module


def test_build_energy_prices_params_includes_dates_area_and_key():
    client = EntsoeClientBase(api_key="test-key")
    start = datetime(2026, 1, 1, 0, 0)
    end = start + timedelta(days=1)

    params = client._build_energy_prices_params(DK1, start, end)

    assert params["documentType"] == "A44"
    assert params["out_Domain"] == DK1.energy_identification_code
    awareness = params["in_Domain"] == DK1.energy_identification_code
    assert awareness
    assert params["periodStart"] == "202601010000"
    assert params["periodEnd"] == "202601020000"
    assert params["securityToken"] == "test-key"


def test_extract_xml_from_zip_filters_xml_files():
    client = EntsoeClientBase(api_key="test-key")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("a.xml", b"<xml>one</xml>")
        zf.writestr("b.txt", b"not xml")
        zf.writestr("c.xml", b"<xml>two</xml>")

    xml_files = client._extract_xml_from_zip(buffer.getvalue())

    assert xml_files == [b"<xml>one</xml>", b"<xml>two</xml>"]


def test_handle_energy_prices_response_plain_xml(monkeypatch):
    def fake_mapper(xml_data: bytes):
        return [xml_data.decode("utf-8")]

    monkeypatch.setattr(client_module, "_parse_energy_prices_xml_to_observation", fake_mapper)

    response = httpx.Response(
        200,
        headers={"Content-Type": "application/xml"},
        content=b"<xml>plain</xml>",
    )

    client = EntsoeClientBase(api_key="test-key")
    result = client._handle_energy_prices_response(response)

    assert result == ["<xml>plain</xml>"]


def test_handle_energy_prices_response_zip(monkeypatch):
    def fake_mapper(xml_data: bytes):
        return [xml_data.decode("utf-8")]

    monkeypatch.setattr(client_module, "_parse_energy_prices_xml_to_observation", fake_mapper)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("one.xml", b"<xml>one</xml>")
        zf.writestr("two.xml", b"<xml>two</xml>")

    response = httpx.Response(
        200,
        headers={"Content-Type": "application/zip"},
        content=buffer.getvalue(),
    )

    client = EntsoeClientBase(api_key="test-key")
    result = client._handle_energy_prices_response(response)

    assert result == ["<xml>one</xml>", "<xml>two</xml>"]


def test_fetch_energy_prices_uses_httpx_and_handler(monkeypatch):
    client = EntsoeClient(api_key="test-key")
    start = datetime(2026, 1, 1, 0, 0)
    end = start + timedelta(days=1)

    captured = {}

    def fake_get(url, params):
        captured["url"] = url
        captured["params"] = params
        return httpx.Response(200, headers={"Content-Type": "application/xml"}, content=b"<xml/>")

    def fake_handler(response):
        return ["handled"]

    monkeypatch.setattr(client_module.httpx, "get", fake_get)
    monkeypatch.setattr(client, "_handle_energy_prices_response", fake_handler)

    result = client.fetch_energy_prices(DK1, start, end)

    assert result == ["handled"]
    assert captured["url"] == client.base_url
    assert captured["params"]["securityToken"] == "test-key"
