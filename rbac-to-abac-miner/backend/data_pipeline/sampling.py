"""Positive/negative sample generation and stratified train/test split.

Algorithm steps 4-7 from the project specification Appendix B:
  S+ = all authorised tuples
  S- = sampled unauthorised tuples (configurable ratio, seed)
  Join user and resource attributes
  Stratified train/test split
"""
from __future__ import annotations

import logging
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from backend.utils.seed import get_rng

logger = logging.getLogger(__name__)


def build_training_samples(
    auth_df: pd.DataFrame,
    users: pd.DataFrame,
    resources: pd.DataFrame,
    user_attribute_columns: list,
    resource_attribute_columns: list,
    ratio: float = 1.0,
    seed: int = 42,
    strategy: str = "random",
) -> Tuple[pd.DataFrame, int, int]:
    """Generate positive and negative samples with user and resource attributes joined.

    S+ = all authorised tuples (authorised == 1).
    S- = sampled unauthorised tuples (authorised == 0), without replacement.
         n_neg = min(ratio * n_pos, available).

    Columns in the returned DataFrame:
        user_id, resource_id, permission,
        user.<attr>..., resource.<attr>..., authorised (1/0).

    Args:
        auth_df: Full authorisation matrix from build_auth_matrix().
                 Columns: user_id, resource_id, permission, authorised.
        users: Users DataFrame with user_id + attribute columns.
        resources: Resources DataFrame with resource_id + attribute columns.
        user_attribute_columns: Names of user attribute columns (no user. prefix).
        resource_attribute_columns: Names of resource attribute columns (no resource. prefix).
        ratio: Desired ratio of negatives to positives. Default 1.0 (1:1).
        seed: Random seed for reproducibility. Default 42.
        strategy: "random" or "stratified" (stratified = proportional per permission).

    Returns:
        Tuple (samples_df, n_pos, n_neg) where samples_df has the joined attribute
        columns, and n_pos / n_neg are the final counts.

    Raises:
        ValueError: On empty auth_df, zero positives, zero negatives, or single class.
    """
    if auth_df.empty:
        raise ValueError("auth_df is empty; cannot generate training samples.")

    positives = auth_df[auth_df["authorised"] == 1].copy()
    negatives_pool = auth_df[auth_df["authorised"] == 0].copy()

    n_pos = len(positives)
    if n_pos == 0:
        raise ValueError(
            "No authorised tuples (S+) found; cannot generate positive samples."
        )

    n_neg_available = len(negatives_pool)
    if n_neg_available == 0:
        raise ValueError(
            "All tuples are authorised (no S- pool); cannot generate negative samples. "
            "This dataset has zero unauthorised tuples."
        )

    n_neg_desired = int(min(ratio * n_pos, n_neg_available))
    if n_neg_desired == 0:
        n_neg_desired = 1  # always sample at least one negative

    rng = get_rng(seed)

    if strategy == "stratified":
        negatives = _stratified_sample(negatives_pool, n_neg_desired, rng)
    else:
        neg_indices = rng.choice(len(negatives_pool), size=n_neg_desired, replace=False)
        negatives = negatives_pool.iloc[neg_indices].copy()

    samples = pd.concat([positives, negatives], ignore_index=True)

    # Join user attributes
    user_attr_cols = ["user_id"] + user_attribute_columns
    users_for_join = users[user_attr_cols].copy()
    rename_map = {c: f"user.{c}" for c in user_attribute_columns}
    users_for_join = users_for_join.rename(columns=rename_map)
    samples = samples.merge(users_for_join, on="user_id", how="left")

    # Join resource attributes
    resource_attr_cols = ["resource_id"] + resource_attribute_columns
    resources_for_join = resources[resource_attr_cols].copy()
    rename_map = {c: f"resource.{c}" for c in resource_attribute_columns}
    resources_for_join = resources_for_join.rename(columns=rename_map)
    samples = samples.merge(resources_for_join, on="resource_id", how="left")

    n_neg = int((samples["authorised"] == 0).sum())
    n_pos_final = int((samples["authorised"] == 1).sum())

    logger.info(
        "Training samples: %d positive, %d negative (%d total), ratio=%.2f, seed=%d",
        n_pos_final, n_neg, len(samples), ratio, seed,
    )

    return samples, n_pos_final, n_neg


def stratified_split(
    samples_df: pd.DataFrame,
    test_size: float = 0.2,
    seed: int = 42,
    label_column: str = "authorised",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified train/test split preserving the class distribution.

    The test split is untouched until final evaluation (no tuning on test data).

    Args:
        samples_df: Full sample DataFrame with a label column.
        test_size: Fraction of samples for the test split. Default 0.2.
        seed: Random seed. Default 42.
        label_column: Name of the binary label column. Default "authorised".

    Returns:
        Tuple (train_df, test_df).

    Raises:
        ValueError: If the split results in a single-class partition.
    """
    if samples_df.empty:
        raise ValueError("samples_df is empty; cannot split.")

    label = samples_df[label_column]
    if label.nunique() < 2:
        raise ValueError(
            f"Only one class present in '{label_column}' column; "
            "cannot produce a stratified split."
        )

    train_df, test_df = train_test_split(
        samples_df,
        test_size=test_size,
        random_state=seed,
        stratify=label,
    )

    train_df = train_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    logger.info(
        "Split: %d train, %d test (test_size=%.2f, seed=%d)",
        len(train_df), len(test_df), test_size, seed,
    )

    return train_df, test_df


def _stratified_sample(
    pool: pd.DataFrame,
    n: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Sample n rows from pool proportionally per unique 'permission' value.

    Args:
        pool: Pool of negative tuples.
        n: Target total sample size.
        rng: NumPy random generator.

    Returns:
        Sampled DataFrame with n rows (or fewer if pool is small).
    """
    permissions = pool["permission"].unique()
    per_perm = max(1, n // len(permissions))
    parts = []
    for perm in permissions:
        sub = pool[pool["permission"] == perm]
        k = min(per_perm, len(sub))
        if k > 0:
            idx = rng.choice(len(sub), size=k, replace=False)
            parts.append(sub.iloc[idx])
    combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=pool.columns)
    # Trim or top-up to exactly n if possible
    if len(combined) > n:
        combined = combined.sample(n=n, random_state=int(rng.integers(0, 2**31))).reset_index(drop=True)
    return combined
