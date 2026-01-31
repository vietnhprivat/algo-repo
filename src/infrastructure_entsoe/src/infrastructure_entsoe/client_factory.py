import os
from .client import EntsoeClient


ENTSOE_API_KEY = "ENTSOE_API_KEY"


def create_entsoe_client() -> EntsoeClient:
    api_key = os.getenv(ENTSOE_API_KEY)
    if not api_key:
        raise ValueError("ENTSOE_API_KEY environment variable is not set.")
    return EntsoeClient(api_key=api_key)
