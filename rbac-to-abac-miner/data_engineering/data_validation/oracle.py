"""
Independent brute-force authorisation oracle and sample verifier.

Public interface:
    brute_force_auth(users_df, roles_df, permissions_df,
                     ua_df, pa_df, resources_df) -> pd.DataFrame
    verify_samples(auth_df, samples_df) -> list[dict]

The oracle is implemented with **plain Python loops** (not pandas merges)
so it is fully independent of Jayed's ``build_auth_matrix`` and
Granthali's ``verify_rbac_authorisation``.  All three must produce the
same result on the small dataset (Milestone 3 acceptance criterion).

Authorisation definition (DATA_PIPELINE.md §2):
    (user_id, resource_id, permission) is authorised iff there exists a
    role r such that (user_id, r) is in UA and a PA row (r, permission,
    [resource_id]) that covers resource_id.

D-001 (permission model):
    permission_id is an action string (e.g. "read").
    role_permissions may have an optional resource_id column:
      - blank / NaN  → the permission applies to ALL resources
      - non-blank    → the permission is scoped to that specific resource_id

Owner : Shweta Suresh Kidile
Ref   : docs/modules/DATA_PIPELINE.md §2, docs/modules/VALIDATION.md §2
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _is_blank(value: Any) -> bool:
    """Return True for None, NaN, empty string, or whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


# ---------------------------------------------------------------------------
# brute_force_auth
# ---------------------------------------------------------------------------
def brute_force_auth(
    users_df: pd.DataFrame,
    roles_df: pd.DataFrame,
    permissions_df: pd.DataFrame,
    ua_df: pd.DataFrame,
    pa_df: pd.DataFrame,
    resources_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute the full RBAC authorisation matrix using plain Python loops.

    Parameters
    ----------
    users_df:       DataFrame with at least column ``user_id``
    roles_df:       DataFrame with at least column ``role_id``
    permissions_df: DataFrame with at least column ``permission_id``
    ua_df:          DataFrame with columns ``user_id``, ``role_id``
    pa_df:          DataFrame with columns ``role_id``, ``permission_id``
                    and optional column ``resource_id`` (blank = all resources)
    resources_df:   DataFrame with at least column ``resource_id``

    Returns
    -------
    pd.DataFrame
        Columns: ``user_id``, ``resource_id``, ``permission``, ``authorised``
        ``authorised`` is ``int`` (1 = authorised, 0 = not authorised).
        Sorted by (user_id, resource_id, permission) for determinism.
        Covers ALL combinations of user × resource × permission.

    Notes
    -----
    - Uses plain loops — independent of pandas merge / Jayed's code.
    - Respects D-001: blank resource_id in PA grants the permission for every resource.
    - Same input → identical output (no random operations).
    """
    # ---- extract lists of ids (plain Python) ----
    user_ids: list[str] = [str(v) for v in users_df["user_id"].tolist()]
    resource_ids: list[str] = [str(v) for v in resources_df["resource_id"].tolist()]
    permission_ids: list[str] = [str(v) for v in permissions_df["permission_id"].tolist()]

    # ---- build lookup: user_id -> set of role_ids ----
    user_to_roles: dict[str, set[str]] = {}
    for _, row in ua_df.iterrows():
        uid = str(row["user_id"])
        rid = str(row["role_id"])
        if uid not in user_to_roles:
            user_to_roles[uid] = set()
        user_to_roles[uid].add(rid)

    # ---- build lookup: role_id -> list of (permission_id, resource_scope) ----
    # resource_scope is None (all resources) or a specific resource_id string
    role_to_perms: dict[str, list[tuple[str, str | None]]] = {}
    for _, row in pa_df.iterrows():
        rid = str(row["role_id"])
        pid = str(row["permission_id"])
        res_raw = row["resource_id"] if "resource_id" in pa_df.columns else None
        res_scope: str | None = None if _is_blank(res_raw) else str(res_raw)
        if rid not in role_to_perms:
            role_to_perms[rid] = []
        role_to_perms[rid].append((pid, res_scope))

    # ---- enumerate all (user, resource, permission) and check auth ----
    rows: list[dict[str, Any]] = []

    for uid in user_ids:
        roles = user_to_roles.get(uid, set())
        for res_id in resource_ids:
            for perm_id in permission_ids:
                authorised = 0
                # Loop over each role the user holds
                for rid in roles:
                    # Loop over each permission granted to that role
                    for (pa_perm, pa_res) in role_to_perms.get(rid, []):
                        if pa_perm == perm_id:
                            # Check resource scope (D-001)
                            if pa_res is None or pa_res == res_id:
                                authorised = 1
                                break   # found a granting path
                    if authorised:
                        break           # no need to check more roles
                rows.append({
                    "user_id": uid,
                    "resource_id": res_id,
                    "permission": perm_id,
                    "authorised": authorised,
                })

    result = pd.DataFrame(rows, columns=["user_id", "resource_id",
                                          "permission", "authorised"])
    result = result.sort_values(
        ["user_id", "resource_id", "permission"]
    ).reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# verify_samples
# ---------------------------------------------------------------------------
def verify_samples(
    auth_df: pd.DataFrame,
    samples_df: pd.DataFrame,
) -> list[dict]:
    """Verify that a samples DataFrame is consistent with the auth matrix.

    Checks (Milestone 4 acceptance criteria):
    1. Every positive row (authorised=1) in samples_df is actually authorised
       in auth_df.
    2. No negative row (authorised=0) in samples_df is authorised in auth_df.
    3. No duplicate (user_id, resource_id, permission, authorised) rows.
    4. The ``authorised`` column exists and contains only 0/1 values.

    Parameters
    ----------
    auth_df:    Full auth matrix — columns: user_id, resource_id,
                permission, authorised (int 0/1).
    samples_df: Sampled dataset — columns include user_id, resource_id,
                permission, authorised.  May have additional attribute
                columns (user.*, resource.*) which are ignored here.

    Returns
    -------
    list[dict]
        List of issue dicts (same shape as ValidationIssue) describing any
        inconsistency.  Empty list = samples are consistent with auth_df.
    """
    issues: list[dict] = []

    # Guard: required columns
    for col in ("user_id", "resource_id", "permission", "authorised"):
        if col not in samples_df.columns:
            issues.append({
                "severity": "error",
                "code": "MISSING_COLUMN",
                "file": "samples_df",
                "row": None,
                "column": col,
                "message": f"samples_df is missing required column '{col}'.",
            })
    if issues:
        return issues

    # Build auth lookup: (user_id, resource_id, permission) -> authorised (0/1)
    auth_lookup: dict[tuple[str, str, str], int] = {}
    for _, row in auth_df.iterrows():
        key = (str(row["user_id"]), str(row["resource_id"]), str(row["permission"]))
        auth_lookup[key] = int(row["authorised"])

    # Check each sample row
    for idx, row in samples_df.iterrows():
        uid = str(row["user_id"])
        res = str(row["resource_id"])
        perm = str(row["permission"])
        label = int(row["authorised"])
        key = (uid, res, perm)
        row_num = int(idx) + 2  # 1-based + header

        if label == 1 and auth_lookup.get(key, 0) == 0:
            issues.append({
                "severity": "error",
                "code": "SAMPLE_LABEL_MISMATCH",
                "file": "samples_df",
                "row": row_num,
                "column": "authorised",
                "message": (
                    f"Row {row_num}: sample is labelled authorised=1 but "
                    f"({uid}, {res}, {perm}) is NOT authorised in the auth matrix."
                ),
            })
        elif label == 0 and auth_lookup.get(key, 0) == 1:
            issues.append({
                "severity": "error",
                "code": "SAMPLE_LABEL_MISMATCH",
                "file": "samples_df",
                "row": row_num,
                "column": "authorised",
                "message": (
                    f"Row {row_num}: sample is labelled authorised=0 but "
                    f"({uid}, {res}, {perm}) IS authorised in the auth matrix."
                ),
            })

    # Check for duplicate (user_id, resource_id, permission, authorised) rows
    dup_cols = ["user_id", "resource_id", "permission", "authorised"]
    dup_mask = samples_df.duplicated(subset=dup_cols, keep="first")
    for idx in samples_df[dup_mask].index:
        issues.append({
            "severity": "warning",
            "code": "DUPLICATE_RECORD",
            "file": "samples_df",
            "row": int(idx) + 2,
            "column": None,
            "message": (
                f"Duplicate sample row at index {int(idx) + 2}."
            ),
        })

    # Check authorised column values are only 0 or 1
    valid_labels = {0, 1}
    for idx, val in samples_df["authorised"].items():
        try:
            if int(val) not in valid_labels:
                issues.append({
                    "severity": "error",
                    "code": "INVALID_VALUE",
                    "file": "samples_df",
                    "row": int(idx) + 2,
                    "column": "authorised",
                    "message": (
                        f"Invalid label value '{val}' at row {int(idx) + 2}. "
                        f"Expected 0 or 1."
                    ),
                })
        except (TypeError, ValueError):
            issues.append({
                "severity": "error",
                "code": "INVALID_TYPE",
                "file": "samples_df",
                "row": int(idx) + 2,
                "column": "authorised",
                "message": (
                    f"Non-integer label '{val}' at row {int(idx) + 2}."
                ),
            })

    return issues
