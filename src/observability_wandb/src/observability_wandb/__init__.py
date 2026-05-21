"""W&B observability layer.

Owns all W&B SDK calls. Other packages depend on this module's
``WandbTracker``; they never import ``wandb`` directly.
"""

from observability_wandb.tracker import WandbTracker as WandbTracker

__all__ = ["WandbTracker"]
