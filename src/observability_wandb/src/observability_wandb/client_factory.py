"""Env-driven W&B settings.

``load_settings()`` reads ``WANDB_API_KEY``, ``WANDB_ENTITY``,
``WANDB_PROJECT``, ``WANDB_MODE`` and returns a ``Settings`` dataclass.

``is_enabled()`` returns ``True`` only when both an API key is present
and ``WANDB_MODE != "disabled"``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_PROJECT = "algo-research"


@dataclass(frozen=True)
class Settings:
    api_key: str
    entity: str
    default_project: str
    mode: str  # "online", "offline", or "disabled"


def load_settings() -> Settings:
    api_key = os.environ.get("WANDB_API_KEY", "")
    entity = os.environ.get("WANDB_ENTITY", "")
    project = os.environ.get("WANDB_PROJECT") or _DEFAULT_PROJECT
    explicit_mode = os.environ.get("WANDB_MODE")
    mode = explicit_mode if explicit_mode else ("online" if api_key else "disabled")
    return Settings(api_key=api_key, entity=entity, default_project=project, mode=mode)


def is_enabled() -> bool:
    settings = load_settings()
    return bool(settings.api_key) and settings.mode != "disabled"
