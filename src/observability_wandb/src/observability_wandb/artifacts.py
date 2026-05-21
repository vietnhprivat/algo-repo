"""Helpers for turning in-memory joblib blobs into W&B Artifacts.

The system stores models as base64 joblib blobs in ``algo.model_artifacts``.
This module decodes such a blob to a temp file then hands it to
``WandbTracker.log_artifact``.
"""

from __future__ import annotations

import base64
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from observability_wandb.tracker import WandbTracker


def log_model_blob(
    *,
    tracker: WandbTracker,
    run: Any,
    artifact_id: str,
    blob_b64: str,
    metadata: Mapping[str, Any],
) -> None:
    """Decode a base64 joblib blob and push it as a W&B model Artifact."""
    if not tracker.is_enabled:
        return None
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / f"{artifact_id}.joblib"
        path.write_bytes(base64.b64decode(blob_b64))
        tracker.log_artifact(
            run=run,
            artifact_id=artifact_id,
            artifact_type="model",
            local_path=str(path),
            metadata=metadata,
        )
