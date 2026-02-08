import os
from pathlib import Path

import clickhouse_connect


CLICKHOUSE_HOST = "CLICKHOUSE_HOST"
CLICKHOUSE_PORT = "CLICKHOUSE_PORT"
CLICKHOUSE_USER = "CLICKHOUSE_USER"
CLICKHOUSE_PASSWORD = "CLICKHOUSE_PASSWORD"

def create_client():
    """Create and return a ClickHouse client using clickhouse-connect.

    Reads from .env (if present) without parsing or casting types. Ensure
    values in .env are in the format expected by clickhouse-connect.
    """

    host = os.getenv(CLICKHOUSE_HOST)
    port = os.getenv(CLICKHOUSE_PORT)
    username = os.getenv(CLICKHOUSE_USER)
    password = os.getenv(CLICKHOUSE_PASSWORD)

    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username,
        password=password,
    )
