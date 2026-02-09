"""ClickHouse infrastructure package."""

from .client_factory import create_client

__all__ = ["create_client"]
