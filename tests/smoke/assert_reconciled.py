"""Final assertion step of the PR smoke: confirm at least one reconciled
experiment_runs row exists after forecast + reconcile have completed."""
import sys

from infrastructure_clickhouse.client_factory import create_client


def main() -> int:
    client = create_client()
    try:
        result = client.query(
            "SELECT count() FROM algo.experiment_runs FINAL "
            "WHERE metrics_json != '{}' AND experiment_name = 'smoke'"
        )
        count = result.result_rows[0][0]
    finally:
        client.close()

    if count < 1:
        print(f"FAIL: expected at least 1 reconciled smoke run, got {count}")
        return 1

    print(f"OK: {count} reconciled smoke run(s) in algo.experiment_runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
