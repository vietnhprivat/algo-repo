from pathlib import Path

from infrastructure_clickhouse.client_factory import create_client


def run_migrations() -> None:
    migrations_dir = Path(__file__).parent
    sql_files = sorted(migrations_dir.glob("*.sql"))

    client = create_client()
    try:
        for sql_file in sql_files:
            sql = sql_file.read_text().strip()
            print(f"Running migration: {sql_file.name}")
            client.command(sql)
            print("  OK")
    finally:
        client.close()


if __name__ == "__main__":
    run_migrations()
