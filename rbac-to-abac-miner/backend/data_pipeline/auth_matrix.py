"""RBAC authorisation matrix builder.

Builds the full (user × resource × permission) authorisation relation from
the six RBAC tables, following the definition:

    (user_id, resource_id, permission) is authorised iff
    ∃ role r : (user_id, r) ∈ UA  AND  (r, permission[, resource_id]) ∈ PA
               where PA resource_id = '' or NaN covers all resources.

Decision D-001: permission is an action; role_permissions may carry an
optional resource_id to scope the permission.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import pandas as pd

from backend.data_pipeline.loader import RBACDataset

logger = logging.getLogger(__name__)


def build_auth_matrix(dataset: RBACDataset) -> pd.DataFrame:
    """Build the full RBAC authorisation matrix.

    Every combination of (user_id, resource_id, permission) is present with
    a binary `authorised` column (1 = authorised, 0 = not).

    The output is sorted by (user_id, resource_id, permission) for
    deterministic ordering.

    Args:
        dataset: Loaded RBACDataset with all six tables populated.

    Returns:
        DataFrame with columns: user_id, resource_id, permission, authorised.
        Size is |U| × |R| × |P|.

    Raises:
        ValueError: If any of the required tables are empty.
    """
    users_df = dataset.users[["user_id"]].drop_duplicates()
    resources_df = dataset.resources[["resource_id"]].drop_duplicates()
    permissions_df = dataset.permissions[["permission_id"]].rename(
        columns={"permission_id": "permission"}
    ).drop_duplicates()
    ua = dataset.user_roles[["user_id", "role_id"]].drop_duplicates()
    pa = dataset.role_permissions[["role_id", "permission_id"] +
                                  (["resource_id"] if "resource_id" in dataset.role_permissions.columns else [])
                                  ].drop_duplicates()

    if users_df.empty:
        raise ValueError("Users table is empty; cannot build authorisation matrix.")
    if resources_df.empty:
        raise ValueError("Resources table is empty; cannot build authorisation matrix.")
    if permissions_df.empty:
        raise ValueError("Permissions table is empty; cannot build authorisation matrix.")

    # Normalise PA resource_id: treat NaN, 'nan', '' as "all resources"
    if "resource_id" not in pa.columns:
        pa = pa.copy()
        pa["resource_id"] = ""
    pa = pa.copy()
    pa["resource_id"] = pa["resource_id"].astype(object).fillna("").astype(str).str.strip()

    # --- Build the set of authorised (user_id, resource_id, permission) tuples ---
    # Step 1: join UA with PA on role_id
    ua_pa = ua.merge(pa, on="role_id", how="inner")
    ua_pa = ua_pa.rename(columns={"permission_id": "permission"})

    # Step 2: for scoped PA rows (resource_id != ''), the tuple is directly authorised
    scoped = ua_pa[ua_pa["resource_id"] != ""][["user_id", "resource_id", "permission"]].copy()

    # Step 3: for unscoped PA rows (resource_id == ''), cross with all resources
    unscoped_users_perms = ua_pa[ua_pa["resource_id"] == ""][["user_id", "permission"]].drop_duplicates()
    if not unscoped_users_perms.empty:
        unscoped_expanded = unscoped_users_perms.merge(
            resources_df.rename(columns={"resource_id": "resource_id"}),
            how="cross",
        )[["user_id", "resource_id", "permission"]]
    else:
        unscoped_expanded = pd.DataFrame(columns=["user_id", "resource_id", "permission"])

    authorised_tuples = (
        pd.concat([scoped, unscoped_expanded], ignore_index=True)
        .drop_duplicates()
        .assign(authorised=1)
    )

    # --- Build the full cross-product matrix ---
    all_tuples = (
        users_df.merge(resources_df, how="cross")
                .merge(permissions_df, how="cross")
    )

    # Merge with authorised tuples
    matrix = all_tuples.merge(
        authorised_tuples, on=["user_id", "resource_id", "permission"], how="left"
    )
    matrix["authorised"] = matrix["authorised"].fillna(0).astype(int)

    # Sort for deterministic output
    matrix = matrix.sort_values(["user_id", "resource_id", "permission"]).reset_index(drop=True)

    n_auth = int(matrix["authorised"].sum())
    n_total = len(matrix)
    logger.info(
        "Auth matrix: %d total tuples, %d authorised (%.1f%%)",
        n_total,
        n_auth,
        100.0 * n_auth / n_total if n_total > 0 else 0.0,
    )

    return matrix


def get_authorisation_roles(
    dataset: RBACDataset,
    user_id: str,
    resource_id: str,
    permission: str,
) -> List[str]:
    """Return the list of roles that grant a given (user, resource, permission) tuple.

    Args:
        dataset: Loaded RBACDataset.
        user_id: Target user.
        resource_id: Target resource.
        permission: Target permission/action.

    Returns:
        List of role_ids that grant access (may be empty).
    """
    ua = dataset.user_roles
    pa = dataset.role_permissions

    user_roles = ua[ua["user_id"] == user_id]["role_id"].unique().tolist()
    if not user_roles:
        return []

    pa_perm = pa[pa["permission_id"] == permission]
    if "resource_id" in pa_perm.columns:
        pa_scope = pa_perm[
            (pa_perm["resource_id"].astype(object).fillna("").astype(str).str.strip() == "")
            | (pa_perm["resource_id"].astype(object).fillna("").astype(str).str.strip() == resource_id)
        ]
    else:
        pa_scope = pa_perm

    granting_roles = pa_scope[pa_scope["role_id"].isin(user_roles)]["role_id"].unique().tolist()
    return granting_roles
