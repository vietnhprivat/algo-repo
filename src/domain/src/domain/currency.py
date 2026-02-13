from enum import Enum


class Currency(str, Enum):
    """European currencies."""

    # Eurozone (20 countries)
    EUR = "EUR"  # Euro

    # Non-Eurozone EU countries
    BGN = "BGN"  # Bulgarian Lev
    CZK = "CZK"  # Czech Koruna
    DKK = "DKK"  # Danish Krone
    HRK = "HRK"  # Croatian Kuna
    HUF = "HUF"  # Hungarian Forint
    PLN = "PLN"  # Polish Zloty
    RON = "RON"  # Romanian Leu
    SEK = "SEK"  # Swedish Krona
    GBP = "GBP"  # British Pound (UK)

    # Non-EU European countries
    CHF = "CHF"  # Swiss Franc
    ISK = "ISK"  # Icelandic Króna
    NOK = "NOK"  # Norwegian Krone
    RUB = "RUB"  # Russian Ruble
    TRY = "TRY"  # Turkish Lira
    UAH = "UAH"  # Ukrainian Hryvnia
    BYN = "BYN"  # Belarusian Ruble
    GEL = "GEL"  # Georgian Lari
    AMD = "AMD"  # Armenian Dram
    AZN = "AZN"  # Azerbaijani Manat

    def __str__(self) -> str:
        """Return the currency code."""
        return self.value
