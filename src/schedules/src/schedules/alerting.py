"""Slack/webhook alerter — used by drift and reconciliation flows.

Posts a Slack-compatible JSON payload to the URL in SLACK_WEBHOOK_URL.
When the env var is unset, the function logs the would-be alert and
returns — keeping dev environments noise-free.
"""
import os

import requests

from infrastructure_clickhouse.logging_setup import get_logger

LOGGER = get_logger(__name__, service="prefect-alerting")

_EMOJI = {
    "info": ":information_source:",
    "warning": ":warning:",
    "error": ":rotating_light:",
}


def notify(*, subject: str, message: str, severity: str = "info") -> None:
    """Post to SLACK_WEBHOOK_URL; no-op if unset."""
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        LOGGER.info(f"[alert noop] {subject}: {message}")
        return
    emoji = _EMOJI.get(severity, ":bell:")
    payload = {"text": f"{emoji} *{subject}*\n{message}"}
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code >= 400:
            LOGGER.warning(f"Slack webhook responded {resp.status_code}")
    except Exception as exc:
        LOGGER.warning(f"Slack notify failed: {exc}")
