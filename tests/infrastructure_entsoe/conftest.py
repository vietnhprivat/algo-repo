"""Fake ENTSOE client and sample XML data for integration tests."""

SAMPLE_ENERGY_PRICES_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
    <mRID>SampleDoc001</mRID>
    <revisionNumber>1</revisionNumber>
    <type>A44</type>
    <sender_MarketParticipant.mRID codingScheme="A01">10X1001A1001A450</sender_MarketParticipant.mRID>
    <sender_MarketParticipant.marketRole.type>A32</sender_MarketParticipant.marketRole.type>
    <receiver_MarketParticipant.mRID codingScheme="A01">10X1001A1001A450</receiver_MarketParticipant.mRID>
    <receiver_MarketParticipant.marketRole.type>A33</receiver_MarketParticipant.marketRole.type>
    <createdDateTime>2024-01-02T00:00:00Z</createdDateTime>
    <period.timeInterval>
        <start>2024-01-01T00:00Z</start>
        <end>2024-01-02T00:00Z</end>
    </period.timeInterval>
    <TimeSeries>
        <mRID>TS001</mRID>
        <businessType>A62</businessType>
        <in_Domain.mRID codingScheme="A01">10Y1001A1001A82H</in_Domain.mRID>
        <out_Domain.mRID codingScheme="A01">10Y1001A1001A82H</out_Domain.mRID>
        <auction.type>A01</auction.type>
        <contract_MarketAgreement.type>A01</contract_MarketAgreement.type>
        <curveType>A03</curveType>
        <currency_Unit.name>EUR</currency_Unit.name>
        <price_Measure_Unit.name>MWH</price_Measure_Unit.name>
        <Period>
            <timeInterval>
                <start>2024-01-01T00:00Z</start>
                <end>2024-01-02T00:00Z</end>
            </timeInterval>
            <resolution>PT60M</resolution>
            <Point><position>1</position><price.amount>50.00</price.amount></Point>
            <Point><position>2</position><price.amount>48.50</price.amount></Point>
            <Point><position>3</position><price.amount>45.00</price.amount></Point>
            <Point><position>4</position><price.amount>42.00</price.amount></Point>
            <Point><position>5</position><price.amount>40.00</price.amount></Point>
            <Point><position>6</position><price.amount>38.50</price.amount></Point>
            <Point><position>7</position><price.amount>41.00</price.amount></Point>
            <Point><position>8</position><price.amount>55.00</price.amount></Point>
            <Point><position>9</position><price.amount>65.00</price.amount></Point>
            <Point><position>10</position><price.amount>70.00</price.amount></Point>
            <Point><position>11</position><price.amount>72.00</price.amount></Point>
            <Point><position>12</position><price.amount>75.00</price.amount></Point>
            <Point><position>13</position><price.amount>73.00</price.amount></Point>
            <Point><position>14</position><price.amount>71.00</price.amount></Point>
            <Point><position>15</position><price.amount>68.00</price.amount></Point>
            <Point><position>16</position><price.amount>66.00</price.amount></Point>
            <Point><position>17</position><price.amount>69.00</price.amount></Point>
            <Point><position>18</position><price.amount>80.00</price.amount></Point>
            <Point><position>19</position><price.amount>85.00</price.amount></Point>
            <Point><position>20</position><price.amount>78.00</price.amount></Point>
            <Point><position>21</position><price.amount>70.00</price.amount></Point>
            <Point><position>22</position><price.amount>60.00</price.amount></Point>
            <Point><position>23</position><price.amount>55.00</price.amount></Point>
            <Point><position>24</position><price.amount>52.00</price.amount></Point>
        </Period>
    </TimeSeries>
</Publication_MarketDocument>
"""


SAMPLE_TOTAL_LOAD_FORECAST_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<GL_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0">
    <mRID>LoadDoc001</mRID>
    <revisionNumber>1</revisionNumber>
    <type>A65</type>
    <process.processType>A01</process.processType>
    <sender_MarketParticipant.mRID codingScheme="A01">10X1001A1001A450</sender_MarketParticipant.mRID>
    <sender_MarketParticipant.marketRole.type>A32</sender_MarketParticipant.marketRole.type>
    <receiver_MarketParticipant.mRID codingScheme="A01">10X1001A1001A450</receiver_MarketParticipant.mRID>
    <receiver_MarketParticipant.marketRole.type>A33</receiver_MarketParticipant.marketRole.type>
    <createdDateTime>2024-01-01T06:00:00Z</createdDateTime>
    <time_Period.timeInterval>
        <start>2024-01-01T00:00Z</start>
        <end>2024-01-02T00:00Z</end>
    </time_Period.timeInterval>
    <TimeSeries>
        <mRID>1</mRID>
        <businessType>A04</businessType>
        <objectAggregation>A01</objectAggregation>
        <outBiddingZone_Domain.mRID codingScheme="A01">10Y1001A1001A82H</outBiddingZone_Domain.mRID>
        <quantity_Measure_Unit.name>MAW</quantity_Measure_Unit.name>
        <curveType>A03</curveType>
        <Period>
            <timeInterval>
                <start>2024-01-01T00:00Z</start>
                <end>2024-01-02T00:00Z</end>
            </timeInterval>
            <resolution>PT60M</resolution>
            <Point><position>1</position><quantity>45000</quantity></Point>
            <Point><position>2</position><quantity>43000</quantity></Point>
            <Point><position>3</position><quantity>41000</quantity></Point>
            <Point><position>4</position><quantity>40000</quantity></Point>
            <Point><position>5</position><quantity>39500</quantity></Point>
            <Point><position>6</position><quantity>40500</quantity></Point>
            <Point><position>7</position><quantity>45000</quantity></Point>
            <Point><position>8</position><quantity>52000</quantity></Point>
            <Point><position>9</position><quantity>58000</quantity></Point>
            <Point><position>10</position><quantity>60000</quantity></Point>
            <Point><position>11</position><quantity>62000</quantity></Point>
            <Point><position>12</position><quantity>63000</quantity></Point>
            <Point><position>13</position><quantity>61000</quantity></Point>
            <Point><position>14</position><quantity>59000</quantity></Point>
            <Point><position>15</position><quantity>57000</quantity></Point>
            <Point><position>16</position><quantity>56000</quantity></Point>
            <Point><position>17</position><quantity>58000</quantity></Point>
            <Point><position>18</position><quantity>65000</quantity></Point>
            <Point><position>19</position><quantity>68000</quantity></Point>
            <Point><position>20</position><quantity>64000</quantity></Point>
            <Point><position>21</position><quantity>58000</quantity></Point>
            <Point><position>22</position><quantity>52000</quantity></Point>
            <Point><position>23</position><quantity>48000</quantity></Point>
            <Point><position>24</position><quantity>46000</quantity></Point>
        </Period>
    </TimeSeries>
</GL_MarketDocument>
"""


class FakeEntsoeResponse:
    """Mimics the shape of an httpx.Response for testing."""

    def __init__(
        self,
        content: bytes = SAMPLE_ENERGY_PRICES_XML,
        status_code: int = 200,
        content_type: str = "application/xml",
    ):
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def decode(self, encoding="utf-8", errors="ignore"):
        return self.content.decode(encoding, errors=errors)
