import pytest
from zoneinfo import ZoneInfo

from domain.areas import (
    Area,
    get_area_from_energy_code,
    get_area_from_tag,
    DE,
    DK1,
    NO,
    COUNTRIES,
    ENERGY_CODE_TO_AREA,
    TAG_TO_AREA,
)


class TestAreaDataclass:
    def test_area_is_frozen(self):
        with pytest.raises(AttributeError):
            DE.tag = "XX"  # type: ignore[misc]

    def test_area_fields(self):
        assert DE.tag == "DE"
        assert DE.name == "Germany"
        assert DE.energy_identification_code == "10Y1001A1001A82H"
        assert DE.country == "DE"
        assert DE.currency == "EUR"
        assert DE.timezone == ZoneInfo("Europe/Berlin")


class TestGetAreaFromEnergyCode:
    def test_returns_correct_area_for_known_code(self):
        area = get_area_from_energy_code("10Y1001A1001A82H")
        assert area is DE

    def test_returns_correct_area_dk1(self):
        area = get_area_from_energy_code("10YDK-1--------W")
        assert area is DK1

    def test_raises_for_unknown_code(self):
        with pytest.raises(ValueError, match="Unknown energy_identification_code"):
            get_area_from_energy_code("UNKNOWN_CODE")


class TestGetAreaFromTag:
    def test_returns_correct_area(self):
        assert get_area_from_tag("NO") is NO
        assert get_area_from_tag("DE") is DE

    def test_raises_for_unknown_tag(self):
        with pytest.raises(ValueError, match="Unknown area tag"):
            get_area_from_tag("ZZ")


class TestLookupConsistency:
    def test_all_countries_in_energy_code_lookup(self):
        for area in COUNTRIES:
            assert area.energy_identification_code in ENERGY_CODE_TO_AREA

    def test_all_countries_in_tag_lookup(self):
        for area in COUNTRIES:
            assert area.tag in TAG_TO_AREA

    def test_round_trip_energy_code(self):
        for area in COUNTRIES:
            retrieved = get_area_from_energy_code(area.energy_identification_code)
            assert retrieved is area

    def test_round_trip_tag(self):
        for area in COUNTRIES:
            retrieved = get_area_from_tag(area.tag)
            assert retrieved is area
