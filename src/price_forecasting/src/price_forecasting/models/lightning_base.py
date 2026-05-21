from __future__ import annotations

import logging
import warnings
from abc import abstractmethod

import lightning as L
import lightning.pytorch.callbacks as L_callbacks
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

from observability_wandb.lightning_logger import build_lightning_logger
from price_forecasting.models.base import BaseModel

logging.getLogger("lightning.pytorch").setLevel(logging.WARNING)
logging.getLogger("lightning").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", module="lightning")


class _BestWeightCallback(L.Callback):
    """In-memory best-weight restoration — no disk I/O."""

    def __init__(self) -> None:
        self.best_val_loss: float = float("inf")
        self.best_state: dict | None = None

    def on_validation_epoch_end(self, trainer: L.Trainer, pl_module: L.LightningModule) -> None:
        val_loss = trainer.callback_metrics.get("val_loss")
        if val_loss is not None:
            loss_value = float(val_loss)
            if loss_value < self.best_val_loss:
                self.best_val_loss = loss_value
                self.best_state = {k: t.clone() for k, t in pl_module.state_dict().items()}


class LightningModel(BaseModel, L.LightningModule):
    """
    Abstract base for PyTorch Lightning models.

    Handles all training boilerplate in fit() and predict_day().
    Subclasses must implement _build_network() and forward().
    Subclasses may override configure_optimizers(), training_step(), validation_step().
    """

    def __init__(
        self,
        epochs: int = 500,
        batch_size: int = 64,
        learning_rate: float = 1e-3,
        l1_reg: float = 0.0,
        validation_fraction: float = 0.2,
        early_stopping_patience: int = 25,
        random_seed: int = 42,
    ) -> None:
        super().__init__()
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.l1_reg = l1_reg
        self.validation_fraction = validation_fraction
        self.early_stopping_patience = early_stopping_patience
        self.random_seed = random_seed
        self._n_periods: int | None = None

    @abstractmethod
    def _build_network(self, n_features: int, n_periods: int) -> None:
        """Build and store the network as a self attribute (e.g. self.net = ...)."""

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor: ...

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.learning_rate)

    def training_step(self, batch, batch_idx):
        x, y = batch
        loss = F.l1_loss(self(x), y)
        if self.l1_reg > 0.0:
            l1_penalty = sum(p.abs().sum() for p in self.parameters())
            loss = loss + self.l1_reg * l1_penalty
        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch
        loss = F.l1_loss(self(x), y)
        self.log("val_loss", loss, prog_bar=False, on_epoch=True, on_step=False)

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        torch.manual_seed(self.random_seed)
        n_samples, n_features = features.shape
        n_periods = targets.shape[1]
        self._n_periods = n_periods

        self._build_network(n_features, n_periods)

        n_val = max(1, int(n_samples * self.validation_fraction))
        n_train = n_samples - n_val

        X_train = torch.tensor(features[:n_train], dtype=torch.float32)
        y_train = torch.tensor(targets[:n_train], dtype=torch.float32)
        X_val = torch.tensor(features[n_train:], dtype=torch.float32)
        y_val = torch.tensor(targets[n_train:], dtype=torch.float32)

        train_loader = DataLoader(
            TensorDataset(X_train, y_train),
            batch_size=min(self.batch_size, n_train),
            shuffle=True,
        )
        val_loader = DataLoader(
            TensorDataset(X_val, y_val),
            batch_size=len(X_val),
            shuffle=False,
        )

        best_weight_cb = _BestWeightCallback()
        early_stop_cb = L_callbacks.EarlyStopping(
            monitor="val_loss",
            patience=self.early_stopping_patience,
            mode="min",
            verbose=False,
        )

        trainer = L.Trainer(
            max_epochs=self.epochs,
            accelerator="auto",
            devices="auto",
            enable_progress_bar=False,
            enable_model_summary=False,
            enable_checkpointing=False,
            logger=build_lightning_logger(getattr(self, "_config", None)) or False,
            log_every_n_steps=1,
            callbacks=[early_stop_cb, best_weight_cb],
        )

        trainer.fit(model=self, train_dataloaders=train_loader, val_dataloaders=val_loader)

        if best_weight_cb.best_state is not None:
            self.load_state_dict(best_weight_cb.best_state)

    def predict_day(self, features: np.ndarray) -> np.ndarray:
        if self._n_periods is None:
            raise RuntimeError(f"{self.__class__.__name__} must be fit before prediction.")
        self.eval()
        device = next(self.parameters()).device
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32).to(device)
            return self(x).squeeze().cpu().numpy()
