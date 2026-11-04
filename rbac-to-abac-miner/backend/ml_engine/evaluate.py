"""Model evaluation utilities.

Evaluates a fitted sklearn classifier on a labelled dataset and returns
ModelMetrics (from shared/schemas/contracts.py).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from shared.schemas.contracts import ModelMetrics

logger = logging.getLogger(__name__)


def evaluate_model(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    training_time_seconds: float = 0.0,
    cv_f1_mean: float | None = None,
    cv_f1_std: float | None = None,
) -> ModelMetrics:
    """Evaluate a fitted classifier and return contract-valid ModelMetrics.

    Args:
        model: Fitted sklearn-compatible classifier (has predict()).
        X: Feature matrix (numpy array).
        y: True labels (numpy array or array-like), binary (0/1).
        training_time_seconds: Wall-clock training time in seconds.
        cv_f1_mean: Mean cross-validation F1 score from training, if available.
        cv_f1_std: Std of cross-validation F1 scores from training, if available.

    Returns:
        ModelMetrics with precision, recall, f1, accuracy, cv stats and timing.

    Raises:
        ValueError: If X and y have mismatched lengths.
    """
    if len(X) != len(y):
        raise ValueError(
            f"X and y length mismatch: {len(X)} vs {len(y)}"
        )

    y_pred = model.predict(X)

    precision = float(precision_score(y, y_pred, zero_division=0))
    recall = float(recall_score(y, y_pred, zero_division=0))
    f1 = float(f1_score(y, y_pred, zero_division=0))
    accuracy = float(accuracy_score(y, y_pred))

    logger.debug(
        "Evaluate: precision=%.4f recall=%.4f f1=%.4f accuracy=%.4f",
        precision, recall, f1, accuracy,
    )

    return ModelMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        cv_f1_mean=cv_f1_mean,
        cv_f1_std=cv_f1_std,
        training_time_seconds=training_time_seconds,
    )
