from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Area:
    """Configuration for a European bidding zone in SDAC coupling."""

    tag: str
    name: str
    energy_identification_code: str
    country: str
    currency: str
    timezone: ZoneInfo


# Nordic countries
NO = Area(
    tag="NO",
    name="Norway",
    energy_identification_code="10YNO-1--------2",
    country="NO",
    currency="NOK",
    timezone=ZoneInfo("Europe/Oslo"),
)

SE = Area(
    tag="SE",
    name="Sweden",
    energy_identification_code="10YSE-1--------K",
    country="SE",
    currency="SEK",
    timezone=ZoneInfo("Europe/Stockholm"),
)

FI = Area(
    tag="FI",
    name="Finland",
    energy_identification_code="10YFI-1--------U",
    country="FI",
    currency="EUR",
    timezone=ZoneInfo("Europe/Helsinki"),
)

DK1 = Area(
    tag="DK1",
    name="Denmark - West",
    energy_identification_code="10YDK-1--------W",
    country="DK",
    currency="DKK",
    timezone=ZoneInfo("Europe/Copenhagen"),
)

DK2 = Area(
    tag="DK2",
    name="Denmark - East",
    energy_identification_code="10YDK-2--------M",
    country="DK",
    currency="DKK",
    timezone=ZoneInfo("Europe/Copenhagen"),
)

# Continental Europe
DE = Area(
    tag="DE",
    name="Germany",
    energy_identification_code="10Y1001A1001A82H",
    country="DE",
    currency="EUR",
    timezone=ZoneInfo("Europe/Berlin"),
)

AT = Area(
    tag="AT",
    name="Austria",
    energy_identification_code="10YAT-APG------L",
    country="AT",
    currency="EUR",
    timezone=ZoneInfo("Europe/Vienna"),
)

CH = Area(
    tag="CH",
    name="Switzerland",
    energy_identification_code="10YCH-SWISSGRID-S",
    country="CH",
    currency="CHF",
    timezone=ZoneInfo("Europe/Zurich"),
)

CZ = Area(
    tag="CZ",
    name="Czech Republic",
    energy_identification_code="10YCZ-CEPS-----N",
    country="CZ",
    currency="CZK",
    timezone=ZoneInfo("Europe/Prague"),
)

SK = Area(
    tag="SK",
    name="Slovakia",
    energy_identification_code="10YSK-SEPS-----K",
    country="SK",
    currency="EUR",
    timezone=ZoneInfo("Europe/Bratislava"),
)

HU = Area(
    tag="HU",
    name="Hungary",
    energy_identification_code="10YHU-MAVIR----U",
    country="HU",
    currency="HUF",
    timezone=ZoneInfo("Europe/Budapest"),
)

RO = Area(
    tag="RO",
    name="Romania",
    energy_identification_code="10YRO-TEL------P",
    country="RO",
    currency="RON",
    timezone=ZoneInfo("Europe/Bucharest"),
)

BG = Area(
    tag="BG",
    name="Bulgaria",
    energy_identification_code="10YCA-BULGARIA-R",
    country="BG",
    currency="BGN",
    timezone=ZoneInfo("Europe/Sofia"),
)

HR = Area(
    tag="HR",
    name="Croatia",
    energy_identification_code="10YHR-HEP------M",
    country="HR",
    currency="HRK",
    timezone=ZoneInfo("Europe/Zagreb"),
)

SI = Area(
    tag="SI",
    name="Slovenia",
    energy_identification_code="10YSI-ELES-----O",
    country="SI",
    currency="EUR",
    timezone=ZoneInfo("Europe/Ljubljana"),
)

# Western Europe
NL = Area(
    tag="NL",
    name="Netherlands",
    energy_identification_code="10YNL----------L",
    country="NL",
    currency="EUR",
    timezone=ZoneInfo("Europe/Amsterdam"),
)

BE = Area(
    tag="BE",
    name="Belgium",
    energy_identification_code="10YBE----------2",
    country="BE",
    currency="EUR",
    timezone=ZoneInfo("Europe/Brussels"),
)

FR = Area(
    tag="FR",
    name="France",
    energy_identification_code="10YFR-RTE------C",
    country="FR",
    currency="EUR",
    timezone=ZoneInfo("Europe/Paris"),
)

GB = Area(
    tag="GB",
    name="Great Britain",
    energy_identification_code="10YGB----------A",
    country="GB",
    currency="GBP",
    timezone=ZoneInfo("Europe/London"),
)

IE = Area(
    tag="IE",
    name="Ireland",
    energy_identification_code="10YIE-1001A00010",
    country="IE",
    currency="EUR",
    timezone=ZoneInfo("Europe/Dublin"),
)

# Southern Europe
ES = Area(
    tag="ES",
    name="Spain",
    energy_identification_code="10YES-REE------0",
    country="ES",
    currency="EUR",
    timezone=ZoneInfo("Europe/Madrid"),
)

PT = Area(
    tag="PT",
    name="Portugal",
    energy_identification_code="10YPT-REN------W",
    country="PT",
    currency="EUR",
    timezone=ZoneInfo("Europe/Lisbon"),
)

IT = Area(
    tag="IT",
    name="Italy",
    energy_identification_code="10YIT-GRTN-----B",
    country="IT",
    currency="EUR",
    timezone=ZoneInfo("Europe/Rome"),
)

GR = Area(
    tag="GR",
    name="Greece",
    energy_identification_code="10YGR-HTSO-----Y",
    country="GR",
    currency="EUR",
    timezone=ZoneInfo("Europe/Athens"),
)

# Eastern Europe
PL = Area(
    tag="PL",
    name="Poland",
    energy_identification_code="10YPL-AREA-----S",
    country="PL",
    currency="PLN",
    timezone=ZoneInfo("Europe/Warsaw"),
)

UA = Area(
    tag="UA",
    name="Ukraine",
    energy_identification_code="10Y1001A1001C---9",
    country="UA",
    currency="UAH",
    timezone=ZoneInfo("Europe/Kyiv"),
)

# Baltic countries
LT = Area(
    tag="LT",
    name="Lithuania",
    energy_identification_code="10YLT-1001A0008Q",
    country="LT",
    currency="EUR",
    timezone=ZoneInfo("Europe/Vilnius"),
)

LV = Area(
    tag="LV",
    name="Latvia",
    energy_identification_code="10YLV-1001A00074",
    country="LV",
    currency="EUR",
    timezone=ZoneInfo("Europe/Riga"),
)

EE = Area(
    tag="EE",
    name="Estonia",
    energy_identification_code="10Y1001A1001B012",
    country="EE",
    currency="EUR",
    timezone=ZoneInfo("Europe/Tallinn"),
)

# Additional countries
XK = Area(
    tag="XK",
    name="Kosovo",
    energy_identification_code="10Y1001C--00098F",
    country="XK",
    currency="EUR",
    timezone=ZoneInfo("Europe/Belgrade"),
)

RS = Area(
    tag="RS",
    name="Serbia",
    energy_identification_code="10YCS-SERBIATSOV",
    country="RS",
    currency="RSD",
    timezone=ZoneInfo("Europe/Belgrade"),
)

BA = Area(
    tag="BA",
    name="Bosnia and Herzegovina",
    energy_identification_code="10Y1001A1001B884",
    country="BA",
    currency="BAM",
    timezone=ZoneInfo("Europe/Sarajevo"),
)

ME = Area(
    tag="ME",
    name="Montenegro",
    energy_identification_code="10Y1001A1001A89L",
    country="ME",
    currency="EUR",
    timezone=ZoneInfo("Europe/Podgorica"),
)

MK = Area(
    tag="MK",
    name="North Macedonia",
    energy_identification_code="10Y1001A1001B86D",
    country="MK",
    currency="MKD",
    timezone=ZoneInfo("Europe/Skopje"),
)

# Set of available countries
COUNTRIES = {
    NO,
    SE,
    FI,
    DK1,
    DK2,
    DE,
    AT,
    CH,
    CZ,
    SK,
    HU,
    RO,
    BG,
    HR,
    SI,
    NL,
    BE,
    FR,
    GB,
    IE,
    ES,
    PT,
    IT,
    GR,
    PL,
    UA,
    LT,
    LV,
    EE,
    XK,
    RS,
    BA,
    ME,
    MK,
}


ENERGY_CODE_TO_AREA = {area.energy_identification_code: area for area in COUNTRIES}
TAG_TO_AREA = {area.tag: area for area in COUNTRIES}


def get_area_from_energy_code(code: str) -> Area:
    """Return Area for an energy_identification_code or raise ValueError."""
    try:
        return ENERGY_CODE_TO_AREA[code]
    except KeyError as exc:
        raise ValueError(f"Unknown energy_identification_code: {code}") from exc


def get_area_from_tag(tag: str) -> Area:
    """Return Area for a tag (e.g., DK1) or raise ValueError."""
    try:
        return TAG_TO_AREA[tag]
    except KeyError as exc:
        raise ValueError(f"Unknown area tag: {tag}") from exc
