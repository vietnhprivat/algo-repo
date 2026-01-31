from datetime import datetime, timedelta

import pandas as pd

import infrastructure_entsoe.mappers as mappers


SAMPLE_XML = b"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Publication_MarketDocument xmlns=\"urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3\">
  <type>A44</type>
  <TimeSeries>
    <mRID>1</mRID>
    <auction.type>A01</auction.type>
    <businessType>A62</businessType>
    <contract_MarketAgreement.type>A01</contract_MarketAgreement.type>
    <curveType>A03</curveType>
    <currency_Unit.name>EUR</currency_Unit.name>
    <price_Measure_Unit.name>MWH</price_Measure_Unit.name>
    <Period>
      <timeInterval>
        <start>2026-01-01T00:00:00+00:00</start>
        <end>2026-01-01T02:00:00+00:00</end>
      </timeInterval>
      <resolution>PT60M</resolution>
      <Point>
        <position>1</position>
        <price.amount>10</price.amount>
      </Point>
      <Point>
        <position>2</position>
        <price.amount>20</price.amount>
      </Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>
"""


def test_map_resolution_to_timedelta():
    assert mappers._map_resolution_to_timedelta("PT15M") == timedelta(minutes=15)
    assert mappers._map_resolution_to_timedelta("PT30M") == timedelta(minutes=30)
    assert mappers._map_resolution_to_timedelta("PT60M") == timedelta(hours=1)
    assert mappers._map_resolution_to_timedelta("P1D") == timedelta(hours=1)


def test_map_A03_curve():
    start = datetime(2026, 1, 1, 0, 0)
    delta = timedelta(hours=1)
    positions = [1, 2, 3]

    mapped = mappers._map_A03_curve(start, delta, positions)

    assert mapped == [
        datetime(2026, 1, 1, 0, 0),
        datetime(2026, 1, 1, 1, 0),
        datetime(2026, 1, 1, 2, 0),
    ]


def test_parse_energy_prices_xml_to_observation(monkeypatch):
    monkeypatch.setattr(mappers, "save_raw_xml_to_file", lambda *args, **kwargs: None)

    result = mappers._parse_energy_prices_xml_to_observation(SAMPLE_XML)

    assert isinstance(result, pd.DataFrame)
    assert list(result["price"]) == [10.0, 20.0]
    assert list(result["auction_type"][:1]) == ["Explicit"]
    assert list(result["business_type"][:1]) == ["Unknown"]
    assert list(result["contract_type"][:1]) == ["Daily"]
    assert result.index.name == "position"

    expected_start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    expected_end = datetime.fromisoformat("2026-01-01T01:00:00+00:00")
    assert result.loc[0, "start_utc"] == expected_start
    assert result.loc[0, "end_utc"] == expected_end
