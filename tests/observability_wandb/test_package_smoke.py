"""Smoke test: package imports without error."""


def test_package_imports() -> None:
    import observability_wandb

    assert hasattr(observability_wandb, "__name__")
