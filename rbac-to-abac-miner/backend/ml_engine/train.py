"""Model training: Decision Tree, Random Forest, Gradient Boosting.

Implements the algorithm steps 8-12 from project specification Appendix B:
  - Train with stratified k-fold CV on the training split only
  - Optional grid/random hyperparameter search inside CV
  - Evaluate once on the held-out test split
  - Mark the Decision Tree as is_rule_extraction_model=True
  - Persist models with joblib

No GPU. No training on the test split. Fixed seeds everywhere.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier

from backend.ml_engine.evaluate import evaluate_model
from shared.schemas.contracts import (
    ModelHyperparams,
    ModelMetrics,
    TrainedModelInfo,
    TrainingConfigRequest,
)

logger = logging.getLogger(__name__)

# Where to persist fitted models (git-ignored directory)
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Decision Tree hyperparameter grid (from config/mining_config.json)
DT_GRID: Dict[str, List[Any]] = {
    "max_depth": [3, 4, 5, 6, 8, 10, None],
    "min_samples_leaf": [1, 2, 5, 10],
    "criterion": ["gini", "entropy"],
}

_MODEL_COUNTER: Dict[str, int] = {}


def _next_model_id(model_type: str) -> str:
    """Generate the next model ID for the given model type.

    Args:
        model_type: Short model type string (e.g. "dt", "rf", "gb").

    Returns:
        ID string such as "m_dt_001".
    """
    _MODEL_COUNTER[model_type] = _MODEL_COUNTER.get(model_type, 0) + 1
    return f"m_{model_type}_{_MODEL_COUNTER[model_type]:03d}"


def _build_base_model(model_name: str, seed: int, hyperparams: Optional[ModelHyperparams] = None) -> Any:
    """Instantiate a base (unfitted) sklearn model.

    Args:
        model_name: One of "decision_tree", "random_forest", "gradient_boosting".
        seed: Random seed.
        hyperparams: Optional hyperparameter overrides.

    Returns:
        Unfitted sklearn estimator.

    Raises:
        ValueError: If model_name is not recognised.
    """
    hp = hyperparams or ModelHyperparams()

    if model_name == "decision_tree":
        kwargs: Dict[str, Any] = dict(random_state=seed, class_weight="balanced")
        if hp.max_depth is not None:
            kwargs["max_depth"] = hp.max_depth
        if hp.min_samples_leaf is not None:
            kwargs["min_samples_leaf"] = hp.min_samples_leaf
        return DecisionTreeClassifier(**kwargs)

    if model_name == "random_forest":
        kwargs = dict(
            n_estimators=hp.n_estimators or 100,
            random_state=seed,
            n_jobs=-1,
            class_weight="balanced",
        )
        if hp.max_depth is not None:
            kwargs["max_depth"] = hp.max_depth
        if hp.min_samples_leaf is not None:
            kwargs["min_samples_leaf"] = hp.min_samples_leaf
        return RandomForestClassifier(**kwargs)

    if model_name == "gradient_boosting":
        kwargs = dict(
            n_estimators=hp.n_estimators or 100,
            learning_rate=hp.learning_rate or 0.1,
            random_state=seed,
        )
        if hp.max_depth is not None:
            kwargs["max_depth"] = hp.max_depth
        return GradientBoostingClassifier(**kwargs)

    raise ValueError(f"Unknown model_name: '{model_name}'")


def train_models(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    config: TrainingConfigRequest,
) -> List[TrainedModelInfo]:
    """Train all requested models, run CV, evaluate on test split.

    Training procedure:
      1. For each model: stratified k-fold CV on the TRAIN split -> cv_f1_mean, cv_f1_std.
      2. If tune_hyperparameters: grid search inside CV on the train split.
      3. Refit on the full train split with chosen params.
      4. Evaluate ONCE on the test split.
      5. Persist with joblib.
      6. Mark Decision Tree as is_rule_extraction_model=True.

    The test split NEVER influences encoder fitting, tuning, model selection or thresholds.

    Args:
        X_train: Encoded feature matrix for training.
        y_train: Training labels (binary 0/1).
        X_test: Encoded feature matrix for testing.
        y_test: Test labels.
        config: TrainingConfigRequest with hyperparams, CV settings, seed etc.

    Returns:
        List of TrainedModelInfo (one per requested model), in order.

    Raises:
        ValueError: If X/y dimensions don't match or no models requested.
    """
    if len(config.models) == 0:
        raise ValueError("No models requested in TrainingConfigRequest.")

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    results: List[TrainedModelInfo] = []

    for model_name in config.models:
        model_type = {"decision_tree": "dt", "random_forest": "rf", "gradient_boosting": "gb"}[model_name]
        model_id = _next_model_id(model_type)
        user_hp = config.hyperparams.get(model_name)

        logger.info("Training model: %s (id=%s)", model_name, model_id)

        cv = StratifiedKFold(n_splits=config.cv_folds, shuffle=True, random_state=config.random_seed)

        if config.tune_hyperparameters and model_name == "decision_tree":
            # Grid search on the train split only
            base = _build_base_model(model_name, config.random_seed)
            gs = GridSearchCV(
                base,
                param_grid=DT_GRID,
                cv=cv,
                scoring="f1",
                n_jobs=-1,
                refit=True,
            )
            t_start = time.perf_counter()
            gs.fit(X_train, y_train)
            training_time = time.perf_counter() - t_start

            fitted_model = gs.best_estimator_
            best_params = gs.best_params_
            cv_f1_mean = float(gs.best_score_)
            cv_scores = gs.cv_results_["mean_test_score"]
            cv_f1_std = float(np.std(cv_scores))
            hyperparams_used: Dict[str, Any] = dict(best_params)
        else:
            base = _build_base_model(model_name, config.random_seed, user_hp)

            # CV on train split only
            cv_scores = cross_val_score(base, X_train, y_train, cv=cv, scoring="f1", n_jobs=-1)
            cv_f1_mean = float(cv_scores.mean())
            cv_f1_std = float(cv_scores.std())

            # Refit on full train split
            t_start = time.perf_counter()
            base.fit(X_train, y_train)
            training_time = time.perf_counter() - t_start
            fitted_model = base
            hyperparams_used = _extract_hyperparams(fitted_model, model_name)

        # Evaluate ONCE on the held-out test split
        metrics = evaluate_model(
            fitted_model,
            X_test,
            y_test,
            training_time_seconds=training_time,
            cv_f1_mean=cv_f1_mean,
            cv_f1_std=cv_f1_std,
        )

        # Persist model
        model_path = _MODELS_DIR / f"{model_id}.joblib"
        joblib.dump(fitted_model, model_path)
        logger.info("Saved %s to %s (f1=%.4f)", model_name, model_path, metrics.f1)

        results.append(
            TrainedModelInfo(
                model_name=model_name,
                model_id=model_id,
                metrics=metrics,
                hyperparams_used=hyperparams_used,
                is_rule_extraction_model=(model_name == "decision_tree"),
            )
        )

    return results


def load_model(model_id: str) -> Any:
    """Load a persisted sklearn model from disk.

    Args:
        model_id: Model ID string (e.g. "m_dt_001").

    Returns:
        Fitted sklearn estimator.

    Raises:
        FileNotFoundError: If the model file does not exist.
    """
    model_path = _MODELS_DIR / f"{model_id}.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    return joblib.load(model_path)


def _extract_hyperparams(model: Any, model_name: str) -> Dict[str, Any]:
    """Extract the hyperparameters actually used by a fitted model.

    Args:
        model: Fitted sklearn estimator.
        model_name: Model name string for labelling.

    Returns:
        Dict of hyperparameter name -> value.
    """
    params = model.get_params()
    if model_name == "decision_tree":
        keep = ["max_depth", "min_samples_leaf", "criterion"]
    elif model_name == "random_forest":
        keep = ["n_estimators", "max_depth", "min_samples_leaf"]
    elif model_name == "gradient_boosting":
        keep = ["n_estimators", "learning_rate", "max_depth"]
    else:
        return {}
    return {k: v for k, v in params.items() if k in keep}
