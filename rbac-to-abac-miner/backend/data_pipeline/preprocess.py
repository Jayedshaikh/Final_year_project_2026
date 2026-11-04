"""Preprocessing and feature encoding for the RBAC-to-ABAC pipeline.

clean_attributes  — normalise and impute attribute DataFrames
encode_features   — one-hot encode categoricals, leave numerics; fit on train only

The encoder stores a feature map so ml_engine.extract_rules can decode tree
split thresholds back to readable attribute conditions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

logger = logging.getLogger(__name__)

# Default missing-value strategies (aligned with config/mining_config.json)
DEFAULT_MISSING_STRATEGY_CATEGORICAL = "category_unknown"
DEFAULT_MISSING_STRATEGY_NUMERIC = "median"


@dataclass
class FeatureEncoder:
    """Wraps the fitted sklearn OneHotEncoder and maps encoded column indices back to conditions.

    Attributes:
        ohe: Fitted OneHotEncoder for categorical columns.
        categorical_cols: Names of categorical columns fed to the OHE.
        numeric_cols: Names of numeric columns kept as-is.
        feature_names: Full ordered list of encoded feature names (OHE output + numeric).
        feature_map: Maps feature index -> (scope, attribute, category | None).
                     scope is "user" or "resource" (stripped from the column prefix).
                     category is the OHE category string, or None for numeric features.
        median_values: Mapping of numeric column -> median computed on training data.
        _fitted: Whether the encoder has been fitted.
    """

    ohe: Optional[OneHotEncoder] = None
    categorical_cols: List[str] = field(default_factory=list)
    numeric_cols: List[str] = field(default_factory=list)
    feature_names: List[str] = field(default_factory=list)
    feature_map: Dict[int, Tuple[str, str, Optional[str]]] = field(default_factory=dict)
    median_values: Dict[str, float] = field(default_factory=dict)
    _fitted: bool = False


def _is_string_col(series: pd.Series) -> bool:
    """Return True if the series contains string / object data (Pandas 2 and 3 compatible).

    Args:
        series: Any pandas Series.

    Returns:
        True for object, string, or StringDtype columns.
    """
    return (
        series.dtype == object
        or series.dtype.name == "string"
        or str(series.dtype) in ("object", "string")
        or pd.api.types.is_string_dtype(series)
    )


def _coerce_numeric(series: pd.Series) -> Optional[pd.Series]:
    """Try to coerce a series to numeric. Returns None if it cannot be coerced.

    Args:
        series: Input series (may be string-typed).

    Returns:
        Numeric series, or None if coercion fails or produces all NaN.
    """
    coerced = pd.to_numeric(series, errors="coerce")
    if coerced.notna().any():
        return coerced
    return None


def clean_attributes(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Normalise and impute an attribute DataFrame.

    - Strips leading/trailing whitespace from string columns.
    - Lower-cases categorical string values (comparison uses lower-case; rule
      conditions carry the original spelling via a lookup — tracked separately).
    - Attempts to coerce string columns that look numeric to float.
    - Imputes missing values per strategy:
        categorical -> "unknown" (configurable)
        numeric     -> column median (configurable)
    - Reports imputed values but never silently discards them.

    Args:
        df: Input DataFrame (may contain user or resource attributes).
        config: Optional config dict (from mining_config.json). Keys:
                "preprocessing.missing_value_strategy.categorical" and
                "preprocessing.missing_value_strategy.numeric".

    Returns:
        Cleaned DataFrame (copy; original is unmodified).
    """
    if config is None:
        config = {}

    cat_strategy = (
        config.get("preprocessing", {})
              .get("missing_value_strategy", {})
              .get("categorical", DEFAULT_MISSING_STRATEGY_CATEGORICAL)
    )
    num_strategy = (
        config.get("preprocessing", {})
              .get("missing_value_strategy", {})
              .get("numeric", DEFAULT_MISSING_STRATEGY_NUMERIC)
    )

    df = df.copy()

    # Identify excluded columns (ids) — they should not be lowercased
    id_cols = {c for c in df.columns if c.endswith("_id")}

    for col in df.columns:
        if col in id_cols:
            # Strip whitespace from IDs but don't lowercase or coerce
            if _is_string_col(df[col]):
                df[col] = df[col].str.strip()
            continue

        if _is_string_col(df[col]):
            # Strip first
            df[col] = df[col].str.strip()

            # Try numeric coercion (e.g. "5", "3.0")
            numeric_try = _coerce_numeric(df[col])
            if numeric_try is not None:
                df[col] = numeric_try
                # Fall through to numeric imputation below
            else:
                # Categorical: lowercase and impute
                df[col] = df[col].str.lower()
                if df[col].isna().any():
                    fill_val = "unknown" if cat_strategy == "category_unknown" else cat_strategy
                    n_missing = int(df[col].isna().sum())
                    logger.warning(
                        "Column '%s': %d missing categorical value(s) imputed with '%s'.",
                        col, n_missing, fill_val,
                    )
                    df[col] = df[col].fillna(fill_val)
                continue  # handled; skip numeric block below

        # Numeric columns (or just-coerced above)
        if pd.api.types.is_numeric_dtype(df[col]):
            if df[col].isna().any():
                if num_strategy == "median":
                    fill_val = float(df[col].median())
                else:
                    try:
                        fill_val = float(num_strategy)
                    except (ValueError, TypeError):
                        fill_val = 0.0
                n_missing = int(df[col].isna().sum())
                logger.warning(
                    "Column '%s': %d missing numeric value(s) imputed with %.4f.",
                    col, n_missing, fill_val,
                )
                df[col] = df[col].fillna(fill_val)

    return df


def encode_features(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_columns: Optional[List[str]] = None,
    label_column: str = "authorised",
) -> Tuple[np.ndarray, np.ndarray, FeatureEncoder]:
    """Encode features for ML training.

    The encoder is FITTED on train_df only (no data leakage).
    test_df is TRANSFORMED using the fitted encoder.

    Categorical columns -> one-hot encoding (handle_unknown='ignore').
    Numeric columns -> kept as-is (cast to float).
    ID columns (user_id, resource_id) are never included as features.

    Args:
        train_df: Training split with feature columns and label column.
        test_df: Test split with the same feature columns.
        feature_columns: Optional explicit list of feature columns. If None,
                         all columns except user_id, resource_id, authorised
                         are used.
        label_column: Name of the label column. Default "authorised".

    Returns:
        Tuple (X_train, X_test, encoder) where X_* are numpy float arrays.

    Raises:
        ValueError: If no feature columns can be identified, or splits are empty.
    """
    EXCLUDE = {"user_id", "resource_id", label_column}

    if feature_columns is None:
        feature_columns = [c for c in train_df.columns if c not in EXCLUDE]

    if not feature_columns:
        raise ValueError("No feature columns found after excluding id and label columns.")

    if train_df.empty:
        raise ValueError("Training split is empty; cannot fit encoder.")

    # Separate categorical vs numeric.
    # After clean_attributes, numeric-looking string columns are already coerced to float.
    # We determine type from the (already-cleaned) train_df.
    cat_cols = []
    num_cols = []
    for c in feature_columns:
        if pd.api.types.is_numeric_dtype(train_df[c]):
            num_cols.append(c)
        elif _is_string_col(train_df[c]):
            # Try coercing: if all parseable as numbers treat as numeric
            coerced = _coerce_numeric(train_df[c])
            if coerced is not None:
                num_cols.append(c)
            else:
                cat_cols.append(c)
        else:
            cat_cols.append(c)

    # Fit OHE on training data only
    encoder = FeatureEncoder()
    encoder.categorical_cols = cat_cols
    encoder.numeric_cols = num_cols

    # Compute medians on training data for any numerics (used by predict-time imputation)
    for col in num_cols:
        col_numeric = pd.to_numeric(train_df[col], errors="coerce")
        encoder.median_values[col] = float(col_numeric.median()) if col_numeric.notna().any() else 0.0

    feature_names: List[str] = []
    feature_map: Dict[int, Tuple[str, str, Optional[str]]] = {}
    idx = 0

    if cat_cols:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32)
        ohe.fit(train_df[cat_cols])
        encoder.ohe = ohe

        for col_idx, col in enumerate(cat_cols):
            cats = ohe.categories_[col_idx]
            scope, attr = _parse_column_name(col)
            for cat in cats:
                encoded_name = f"{col}={cat}"
                feature_names.append(encoded_name)
                feature_map[idx] = (scope, attr, str(cat))
                idx += 1

    for col in num_cols:
        feature_names.append(col)
        scope, attr = _parse_column_name(col)
        feature_map[idx] = (scope, attr, None)
        idx += 1

    encoder.feature_names = feature_names
    encoder.feature_map = feature_map
    encoder._fitted = True

    X_train = _transform(train_df, encoder, feature_columns)
    X_test = _transform(test_df, encoder, feature_columns)

    logger.info(
        "Encoded features: %d categorical (-> %d OHE cols) + %d numeric = %d total features",
        len(cat_cols),
        sum(len(ohe.categories_[i]) for i in range(len(cat_cols))) if cat_cols else 0,
        len(num_cols),
        X_train.shape[1],
    )

    return X_train, X_test, encoder


def _transform(df: pd.DataFrame, encoder: FeatureEncoder, feature_columns: List[str]) -> np.ndarray:
    """Apply a fitted FeatureEncoder to a DataFrame.

    Args:
        df: DataFrame with feature columns.
        encoder: A fitted FeatureEncoder.
        feature_columns: The ordered list of feature columns.

    Returns:
        numpy array of float32 with shape (n_samples, n_features).
    """
    parts = []

    if encoder.categorical_cols and encoder.ohe is not None:
        cat_data = df[encoder.categorical_cols].copy()
        # Ensure string type for OHE
        for col in encoder.categorical_cols:
            cat_data[col] = cat_data[col].astype(str).fillna("unknown")
        parts.append(encoder.ohe.transform(cat_data))

    if encoder.numeric_cols:
        num_data = df[encoder.numeric_cols].copy()
        for col in encoder.numeric_cols:
            col_series = pd.to_numeric(num_data[col], errors="coerce")
            med = encoder.median_values.get(col, 0.0)
            num_data[col] = col_series.fillna(med)
        parts.append(num_data.values.astype(np.float32))

    if not parts:
        return np.empty((len(df), 0), dtype=np.float32)

    return np.hstack(parts).astype(np.float32)


def _parse_column_name(col: str) -> Tuple[str, str]:
    """Parse a column name into (scope, attribute).

    Columns may be prefixed as "user.<attr>" or "resource.<attr>".
    Unprefixed columns (e.g. "permission") return ("", col).

    Args:
        col: Column name string.

    Returns:
        Tuple (scope, attribute).
    """
    if col.startswith("user."):
        return "user", col[len("user."):]
    if col.startswith("resource."):
        return "resource", col[len("resource."):]
    return "", col
