import os

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

CLICKHOUSE_HOST = "CLICKHOUSE_HOST"
CLICKHOUSE_PORT = "CLICKHOUSE_PORT"
CLICKHOUSE_USER = "CLICKHOUSE_USER"
CLICKHOUSE_PASSWORD = "CLICKHOUSE_PASSWORD"
CLICKHOUSE_DATABASE = "CLICKHOUSE_DATABASE"


def create_client():
    """Create and return a ClickHouse client using environment variables."""
    host = os.getenv(CLICKHOUSE_HOST, "localhost")
    port = int(os.getenv(CLICKHOUSE_PORT, "8123"))
    username = os.getenv(CLICKHOUSE_USER, "default")
    password = os.getenv(CLICKHOUSE_PASSWORD, "password")
    database = os.getenv(CLICKHOUSE_DATABASE, "algo")

    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )
