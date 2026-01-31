import pytest

from infrastructure_entsoe.client_factory import create_entsoe_client, ENTSOE_API_KEY


def test_create_entsoe_client_requires_env_var(monkeypatch):
    monkeypatch.delenv(ENTSOE_API_KEY, raising=False)

    with pytest.raises(ValueError, match="ENTSOE_API_KEY environment variable is not set"):
        create_entsoe_client()


def test_create_entsoe_client_reads_env_var(monkeypatch):
    monkeypatch.setenv(ENTSOE_API_KEY, "test-key")

    client = create_entsoe_client()

    assert client.api_key == "test-key"
