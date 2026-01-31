from enum import Enum
from typing import Optional


# https://transparencyplatform.zendesk.com/hc/en-us/articles/15857039772052-ProcessType
class ProcessType(Enum):
    Dayahead = 'A01'
    IntradayIncremental = 'A02'
    Realised = 'A16'
    IntradayTotal = 'A18'
    WeekAhead = 'A31'
    MonthAhead = 'A32'
    YearAhead = 'A33'
    SynchronisationProcess = 'A39'
    Intraday = 'A40'
    ReplacementReserve = 'A46' # was A47
    ManualFrequencyRestorationReserve = 'A47'
    AutomaticFrequencyRestorationReserve = 'A51'
    FrequencyContainmentReserve = 'A52'
    FrequencyRestorationReserve = 'A56'
    ScheduledActivationMFRR = 'A60'
    DirectActivationMFRR = 'A61'
    CentralSelectionAFRR = 'A67'
    LocalSelectionAFRR = 'A68'


    @classmethod
    def from_str(cls, name: str) -> Optional["ProcessType"]:
        normalized = name.lower()
        for member in cls:
            if member.name.lower() == normalized:
                return member

        return None


# https://transparencyplatform.zendesk.com/hc/en-us/articles/15856995130004-PsrType
class PsrType(Enum):
    Mixed = 'A03'
    Generation = 'A04'
    Load = 'A05'
    Biomass = 'B01'
    FossilBrowncoalAndLignite = 'B02'
    FossilCoalDerivedGas = 'B03'
    FossilGas = 'B04'
    FossilHardCoal = 'B05'
    FossilOil = 'B06'
    FossilOilShale = 'B07'
    FossilPeat = 'B08'
    Geothermal = 'B09'
    HydroPumpedStorage = 'B10'
    HydroRunOfRiverAndPoundage = 'B11'
    HydroWaterReservoir = 'B12'
    Marine = 'B13'
    Nuclear = 'B14'
    OtherRenewable = 'B15'
    SOLAR = 'B16'
    Waste = 'B17'
    WIND_OFFSHORE = 'B18'
    WIND_ONSHORE = 'B19'
    Other = 'B20'
    ACLink = 'B21'
    DCLink = 'B22'
    Substation = 'B23'
    Transformer = 'B24'
    EnergyStorage = 'B25'


# https://transparencyplatform.zendesk.com/hc/en-us/articles/15857010932500-BusinessType
class BusinessType(Enum):
    Production = 'A01'
    Consumption = 'A04'
    BalanceEnergyDeviation = 'A19'
    GeneralCapacityInformation = 'A25'
    AlreadyAllocatedCapacity = 'A29'
    InstalledGeneration = 'A37'
    RequestedCapacityWithoutPrice = 'A43'
    SystemOperatorRedispatching = 'A46'
    PlannedMaintenance = 'A53'
    UnplannedOutage = 'A54'
    MinimumPossible = 'A60'
    MaximumPossible = 'A61'
    InternalRedispatch = 'A85'
    PositiveForecastMargin = 'A91'
    NegativeForecastMargin = 'A92'
    WindGeneration = 'A93'
    SolarGeneration = 'A94'
    FrequencyContainmentReserve = 'A95'
    AutomaticFrequencyRestorationReserve = 'A96'
    ManualFrequencyRestorationReserve = 'A97'
    ReplacementReserve = 'A98'
    InterconnectorNetworkEvolution = 'B01'
    InterconnectorNetworkDismantling = 'B02'
    CounterTrade = 'B03'
    CongestionCosts = 'B04'
    CapacityAllocatedIncludingPrice = 'B05'
    AuctionRevenue = 'B07'
    TotalNominatedCapacity = 'B08'
    NetPosition = 'B09'
    CongestionIncome = 'B10'
    ProductionUnit = 'B11'
    AreaControlError = 'B33'
    Offer = 'B74'
    Need = 'B75'
    ProcuredCapacity = 'B95'
    SharedBalancingReserveCapacity = 'C22'
    ShareOfReserveCapacity = 'C23'
    ActualReserveCapacity = 'C24'
    ForecastedCapacity = 'C76'
    Min = 'C77'
    Average = 'C78'
    Max = 'C79'
    Unknown = 'A62'

# https://transparencyplatform.zendesk.com/hc/en-us/articles/15856954661012-Type-MarketAgreement-Type
class MarketAgreementType(Enum):
    Daily = 'A01'
    Weekly = 'A02'
    Monthly = 'A03'
    Yearly = 'A04'
    Total = 'A05'
    LongTerm = 'A06'
    Intraday = 'A07'
    Hourly = 'A13'

# https://transparencyplatform.zendesk.com/hc/en-us/articles/15857089373076-Standard-MarketProduct
# https://transparencyplatform.zendesk.com/hc/en-us/articles/15857105955988-Original-MarketProduct
# Standard-MarketProduct and Orignal-MarketProduct mapping are identical
class MarketProduct(Enum):
    Standard = 'A01'
    Specific = 'A02'
    IntegratedProcess = 'A03'
    Local = "A04"
    StandardMFRR_DA = 'A05'
    StandardMFRR_SA_DA = 'A07'

# https://transparencyplatform.zendesk.com/hc/en-us/articles/15857071081620-flowDirection-direction
class FlowDirection(Enum):
    Up = "A01"
    Down = "A02"
    Symmetric = "A03"

class AuctionType(Enum):
    Explicit = "A01"
    Implicit = "A02"


# https://transparencyplatform.zendesk.com/hc/en-us/articles/15857043092756-DocumentType
class DocumentType(Enum):
    FinalizedSchedule = "A09"
    AggregatedEnergyDataReport = "A11"
    AcquiringSystemOperatorReserveSchedule = "A15"
    BidDocument = "A24"
    AllocationResultDocument = "A25"
    CapacityDocument = "A26"
    AgreedCapacity = "A31"
    ReserveBidDocument = "A37"
    ReserveAllocationResultDocument = "A38"
    PriceDocument = "A44"
    EstimatedNetTransferCapacity = "A61"
    RedispatchNotice = "A63"
    SystemTotalLoad = "A65"
    InstalledGenerationPerType = "A68"
    WindAndSolarForecast = "A69"
    LoadForecastMargin = "A70"
    GenerationForecast = "A71"
    ReservoirFillingInformation = "A72"
    ActualGeneration = "A73"
    WindAndSolarGeneration = "A74"
    ActualGenerationPerType = "A75"
    LoadUnavailability = "A76"
    ProductionUnavailability = "A77"
    TransmissionUnavailability = "A78"
    OffshoreGridInfrastructureUnavailability = "A79"
    GenerationUnavailability = "A80"
    ContractedReserves = "A81"
    AcceptedOffers = "A82"
    ActivatedBalancingQuantities = "A83"
    ActivatedBalancingPrices = "A84"
    ImbalancePrices = "A85"
    ImbalanceVolume = "A86"
    FinancialSituation = "A87"
    CrossBorderBalancing = "A88"
    ContractedReservePrices = "A89"
    InterconnectionNetworkExpansion = "A90"
    CounterTradeNotice = "A91"
    CongestionCosts = "A92"
    DCLinkCapacity = "A93"
    NonEUAllocations = "A94"
    ConfigurationDocument = "A95"
    FlowBasedAllocations = "B11"
    AggregatedNettedExternalTSOScheduleDocument = "B17"
    BidAvailabilityDocument = "B45"