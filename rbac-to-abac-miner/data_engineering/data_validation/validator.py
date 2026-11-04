"""
Dataset validation library.

Public interface:
    validate_dataset(files: dict[str, pd.DataFrame]) -> list[dict]

Each returned dict has exactly the fields of ``ValidationIssue`` from
``shared/schemas/contracts.py``:
    severity : "error" | "warning"
    code     : str   (see VALIDATION.md §1 for the full code list)
    file     : str   (e.g. "users.csv")
    row      : int | None
    column   : str | None
    message  : str

Any ``severity == "error"`` means the dataset is invalid and the caller
should set ``status = "invalid"`` with ``dataset_id = null``.

This module is importable **without** the backend (no FastAPI / scikit-learn
imports). Only ``pandas`` and Python stdlib are required.

Owner : Shweta Suresh Kidile
Ref   : docs/modules/VALIDATION.md §1, docs/modules/DATA_PIPELINE.md §1
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Issue code constants  (mirror VALIDATION.md §1)
# ---------------------------------------------------------------------------
MISSING_FILE = "MISSING_FILE"
EMPTY_FILE = "EMPTY_FILE"
MISSING_COLUMN = "MISSING_COLUMN"
DUPLICATE_KEY = "DUPLICATE_KEY"
DUPLICATE_RECORD = "DUPLICATE_RECORD"
DANGLING_REFERENCE = "DANGLING_REFERENCE"
MISSING_VALUE = "MISSING_VALUE"
INVALID_TYPE = "INVALID_TYPE"
INVALID_VALUE = "INVALID_VALUE"
USER_WITHOUT_ROLE = "USER_WITHOUT_ROLE"
ROLE_WITHOUT_PERMISSION = "ROLE_WITHOUT_PERMISSION"
SINGLE_CLASS = "SINGLE_CLASS"

# ---------------------------------------------------------------------------
# Required tables and their required columns  (DATA_PIPELINE.md §1)
# ---------------------------------------------------------------------------
REQUIRED_TABLES: list[str] = [
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "resources",
]

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "users":            ["user_id"],
    "roles":            ["role_id"],
    "permissions":      ["permission_id"],
    "user_roles":       ["user_id", "role_id"],
    "role_permissions": ["role_id", "permission_id"],
    "resources":        ["resource_id"],
}

# Primary key column for each entity table
PRIMARY_KEYS: dict[str, str] = {
    "users":       "user_id",
    "roles":       "role_id",
    "permissions": "permission_id",
    "resources":   "resource_id",
}

# Columns that must be numeric when present
NUMERIC_COLUMNS: dict[str, list[str]] = {
    "users": ["seniority"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _issue(
    severity: str,
    code: str,
    file: str,
    row: int | None = None,
    column: str | None = None,
    message: str = "",
) -> dict[str, Any]:
    """Construct a ValidationIssue-shaped dict."""
    return {
        "severity": severity,
        "code": code,
        "file": file,
        "row": row,
        "column": column,
        "message": message,
    }


def _is_blank(value: Any) -> bool:
    """Return True for None, NaN, empty string, whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------
def validate_dataset(files: dict[str, pd.DataFrame]) -> list[dict]:
    """Validate a set of RBAC tables and return a list of ValidationIssue dicts.

    Parameters
    ----------
    files:
        Mapping of table name → DataFrame.  Expected keys:
        ``users``, ``roles``, ``permissions``, ``user_roles``,
        ``role_permissions``, ``resources``.

    Returns
    -------
    list[dict]
        Each dict has keys ``severity``, ``code``, ``file``, ``row``,
        ``column``, ``message``.  Empty list means no issues (valid dataset).
        The caller wraps each dict with ``ValidationIssue(**d)`` from
        ``shared/schemas/contracts.py``.

    Notes
    -----
    - Never raises; all errors are collected and returned.
    - Importable without the backend (no FastAPI / scikit-learn imports).
    - Checks run in dependency order: structural checks first, then semantic.
    """
    issues: list[dict] = []

    # ------------------------------------------------------------------
    # 1. MISSING_FILE — check all six tables are present
    # ------------------------------------------------------------------
    for table in REQUIRED_TABLES:
        if table not in files:
            issues.append(_issue(
                severity="error",
                code=MISSING_FILE,
                file=f"{table}.csv",
                message=f"Required table '{table}' was not provided.",
            ))

    # If any table is missing we cannot run referential checks safely.
    # Return early with what we have so far only if core tables are missing.
    present = {k: v for k, v in files.items() if k in REQUIRED_TABLES}
    if len(present) < len(REQUIRED_TABLES):
        # Still run per-table checks on what we do have
        for table, df in present.items():
            issues.extend(_check_table(table, df))
        return issues

    # ------------------------------------------------------------------
    # 2. Per-table structural checks
    # ------------------------------------------------------------------
    for table in REQUIRED_TABLES:
        df = files[table]
        issues.extend(_check_table(table, df))

    # If there are errors in structural checks, referential checks will
    # likely produce spurious results — but we run them anyway and let
    # the caller decide.  Short-circuit only when a table is empty.
    users_df = files["users"]
    roles_df = files["roles"]
    perms_df = files["permissions"]
    ur_df = files["user_roles"]
    rp_df = files["role_permissions"]
    res_df = files["resources"]

    # ------------------------------------------------------------------
    # 3. DANGLING_REFERENCE checks
    # Guard: only run if the referenced id column actually exists in the
    # entity table (it may have been reported missing above).
    # ------------------------------------------------------------------
    if "user_id" in users_df.columns:
        issues.extend(_check_dangling(ur_df, "user_roles", "user_id",
                                      users_df["user_id"], "users.csv"))
    if "role_id" in roles_df.columns:
        issues.extend(_check_dangling(ur_df, "user_roles", "role_id",
                                      roles_df["role_id"], "roles.csv"))
        issues.extend(_check_dangling(rp_df, "role_permissions", "role_id",
                                      roles_df["role_id"], "roles.csv"))
    if "permission_id" in perms_df.columns:
        issues.extend(_check_dangling(rp_df, "role_permissions", "permission_id",
                                      perms_df["permission_id"], "permissions.csv"))

    # resource_id in role_permissions is optional (blank = all resources)
    if "resource_id" in rp_df.columns:
        known_resources = set(res_df["resource_id"].astype(str))
        for idx, row_val in rp_df["resource_id"].items():
            if _is_blank(row_val):
                continue  # blank = all resources (D-001)
            if str(row_val) not in known_resources:
                issues.append(_issue(
                    severity="error",
                    code=DANGLING_REFERENCE,
                    file="role_permissions.csv",
                    row=int(idx) + 2,  # 1-based + header
                    column="resource_id",
                    message=(
                        f"resource_id '{row_val}' not found in resources.csv"
                    ),
                ))

    # ------------------------------------------------------------------
    # 4. USER_WITHOUT_ROLE
    # ------------------------------------------------------------------
    if ("user_id" in ur_df.columns and "user_id" in users_df.columns
            and len(users_df) > 0):
        assigned_users = set(ur_df["user_id"].astype(str))
        for uid in users_df["user_id"].astype(str):
            if uid not in assigned_users:
                issues.append(_issue(
                    severity="warning",
                    code=USER_WITHOUT_ROLE,
                    file="user_roles.csv",
                    column="user_id",
                    message=(
                        f"user_id '{uid}' has no entry in user_roles "
                        f"and will never be authorised."
                    ),
                ))

    # ------------------------------------------------------------------
    # 5. ROLE_WITHOUT_PERMISSION
    # ------------------------------------------------------------------
    if ("role_id" in rp_df.columns and "role_id" in roles_df.columns
            and len(roles_df) > 0):
        roles_with_perms = set(rp_df["role_id"].astype(str))
        for rid in roles_df["role_id"].astype(str):
            if rid not in roles_with_perms:
                issues.append(_issue(
                    severity="warning",
                    code=ROLE_WITHOUT_PERMISSION,
                    file="role_permissions.csv",
                    column="role_id",
                    message=(
                        f"role_id '{rid}' grants no permissions "
                        f"and its users will never be authorised."
                    ),
                ))

    # ------------------------------------------------------------------
    # 6. SINGLE_CLASS — check whether the auth matrix has both classes
    # This runs even if relation tables are empty (empty user_roles = all negative).
    # ------------------------------------------------------------------
    issues.extend(_check_single_class(
        users_df, roles_df, perms_df, ur_df, rp_df, res_df
    ))

    return issues


# ---------------------------------------------------------------------------
# Per-table checks
# ---------------------------------------------------------------------------
def _check_table(table: str, df: pd.DataFrame) -> list[dict]:
    """Run structural checks on a single table."""
    issues: list[dict] = []
    file_name = f"{table}.csv"

    # EMPTY_FILE
    if len(df) == 0:
        issues.append(_issue(
            severity="error",
            code=EMPTY_FILE,
            file=file_name,
            message=f"Table '{table}' has no rows.",
        ))
        return issues  # Cannot check columns/keys on an empty frame

    # MISSING_COLUMN
    required = REQUIRED_COLUMNS.get(table, [])
    for col in required:
        if col not in df.columns:
            issues.append(_issue(
                severity="error",
                code=MISSING_COLUMN,
                file=file_name,
                column=col,
                message=f"Required column '{col}' is missing from '{table}'.",
            ))

    # DUPLICATE_KEY (entity tables only)
    if table in PRIMARY_KEYS:
        pk = PRIMARY_KEYS[table]
        if pk in df.columns:
            dupes = df[df.duplicated(subset=[pk], keep=False)]
            seen: set[str] = set()
            for idx, row in dupes.iterrows():
                val = str(row[pk])
                if val not in seen:
                    seen.add(val)
                    issues.append(_issue(
                        severity="error",
                        code=DUPLICATE_KEY,
                        file=file_name,
                        row=int(idx) + 2,
                        column=pk,
                        message=(
                            f"Duplicate {pk} '{val}' in '{table}'. "
                            f"Primary keys must be unique."
                        ),
                    ))

    # DUPLICATE_RECORD (relation tables)
    if table in ("user_roles", "role_permissions"):
        key_cols = REQUIRED_COLUMNS.get(table, list(df.columns))
        existing_cols = [c for c in key_cols if c in df.columns]
        if existing_cols:
            dupe_mask = df.duplicated(subset=existing_cols, keep="first")
            for idx in df[dupe_mask].index:
                issues.append(_issue(
                    severity="warning",
                    code=DUPLICATE_RECORD,
                    file=file_name,
                    row=int(idx) + 2,
                    message=(
                        f"Duplicate record at row {int(idx) + 2} in '{table}' "
                        f"(columns {existing_cols}). The duplicate will be ignored."
                    ),
                ))

    # MISSING_VALUE — attribute columns (non-required / non-id columns)
    id_cols = set(REQUIRED_COLUMNS.get(table, []))
    for col in df.columns:
        if col in id_cols:
            continue
        for idx, val in df[col].items():
            if _is_blank(val):
                issues.append(_issue(
                    severity="warning",
                    code=MISSING_VALUE,
                    file=file_name,
                    row=int(idx) + 2,
                    column=col,
                    message=(
                        f"Missing value in '{col}' at row {int(idx) + 2}. "
                        f"Will be imputed with 'unknown' (categorical) or "
                        f"median (numeric)."
                    ),
                ))

    # INVALID_TYPE — columns expected to be numeric
    numeric_cols = NUMERIC_COLUMNS.get(table, [])
    for col in numeric_cols:
        if col not in df.columns:
            continue
        for idx, val in df[col].items():
            if _is_blank(val):
                continue  # already caught as MISSING_VALUE
            try:
                float(val)
            except (TypeError, ValueError):
                issues.append(_issue(
                    severity="error",
                    code=INVALID_TYPE,
                    file=file_name,
                    row=int(idx) + 2,
                    column=col,
                    message=(
                        f"Non-numeric value '{val}' in column '{col}' "
                        f"at row {int(idx) + 2}. Expected a number."
                    ),
                ))

    # INVALID_VALUE — negative seniority
    if table == "users" and "seniority" in df.columns:
        for idx, val in df["seniority"].items():
            if _is_blank(val):
                continue
            try:
                num = float(val)
                if num < 0:
                    issues.append(_issue(
                        severity="warning",
                        code=INVALID_VALUE,
                        file=file_name,
                        row=int(idx) + 2,
                        column="seniority",
                        message=(
                            f"Negative seniority value '{val}' at row "
                            f"{int(idx) + 2}. Seniority must be >= 0."
                        ),
                    ))
            except (TypeError, ValueError):
                pass  # already caught by INVALID_TYPE above

    return issues


# ---------------------------------------------------------------------------
# Dangling reference check helper
# ---------------------------------------------------------------------------
def _check_dangling(
    rel_df: pd.DataFrame,
    rel_table: str,
    fk_col: str,
    valid_ids: pd.Series,
    target_file: str,
) -> list[dict]:
    """Check that every value in *fk_col* of *rel_df* exists in *valid_ids*."""
    issues: list[dict] = []
    if fk_col not in rel_df.columns:
        return issues
    known = set(valid_ids.astype(str))
    for idx, val in rel_df[fk_col].items():
        if _is_blank(val):
            continue
        if str(val) not in known:
            issues.append(_issue(
                severity="error",
                code=DANGLING_REFERENCE,
                file=f"{rel_table}.csv",
                row=int(idx) + 2,
                column=fk_col,
                message=(
                    f"{fk_col} '{val}' not found in {target_file}."
                ),
            ))
    return issues


# ---------------------------------------------------------------------------
# SINGLE_CLASS check — requires computing the auth relation
# ---------------------------------------------------------------------------
def _check_single_class(
    users_df: pd.DataFrame,
    roles_df: pd.DataFrame,
    perms_df: pd.DataFrame,
    ur_df: pd.DataFrame,
    rp_df: pd.DataFrame,
    res_df: pd.DataFrame,
) -> list[dict]:
    """Return a SINGLE_CLASS error if the dataset has only one label class.

    Performs a lightweight auth check (loops, independent of Jayed's code)
    to count authorised vs. unauthorised tuples.  If all tuples are
    authorised, or none are, a supervised classifier cannot be trained.

    Handles empty relation tables (user_roles or role_permissions with 0 rows)
    gracefully — these result in all-negative (no authorisations) correctly.
    """
    # Guard: need entity tables to be non-empty with required id columns
    if (len(users_df) == 0 or len(roles_df) == 0 or len(perms_df) == 0
            or len(res_df) == 0):
        return []  # EMPTY_FILE errors already reported; can't compute matrix

    required_entity_cols = (
        "user_id" in users_df.columns
        and "role_id" in roles_df.columns
        and "permission_id" in perms_df.columns
        and "resource_id" in res_df.columns
    )
    if not required_entity_cols:
        return []  # MISSING_COLUMN errors already reported

    # Handle empty relation tables — means no authorisations (all negative)
    if len(ur_df) == 0 or len(rp_df) == 0:
        n_total = (len(users_df) * len(res_df) * len(perms_df))
        if n_total == 0:
            return []
        return [_issue(
            severity="error",
            code=SINGLE_CLASS,
            file="user_roles.csv" if len(ur_df) == 0 else "role_permissions.csv",
            message=(
                "No authorised tuples found in the dataset (empty relation table). "
                "A classifier cannot be trained on single-class data (all negative)."
            ),
        )]

    # Also need relation columns present
    required_relation_cols = (
        "user_id" in ur_df.columns and "role_id" in ur_df.columns
        and "role_id" in rp_df.columns and "permission_id" in rp_df.columns
    )
    if not required_relation_cols:
        return []

    # Build fast lookup structures
    user_roles: dict[str, set[str]] = {}
    for _, row in ur_df.iterrows():
        uid = str(row["user_id"])
        rid = str(row["role_id"])
        user_roles.setdefault(uid, set()).add(rid)

    # role_id -> list of (permission_id, resource_id or None)
    role_perms: dict[str, list[tuple[str, str | None]]] = {}
    for _, row in rp_df.iterrows():
        rid = str(row["role_id"])
        pid = str(row["permission_id"])
        res = row.get("resource_id", None)
        res_scoped = None if _is_blank(res) else str(res)
        role_perms.setdefault(rid, []).append((pid, res_scoped))

    user_ids = users_df["user_id"].astype(str).tolist()
    resource_ids = res_df["resource_id"].astype(str).tolist()
    permission_ids = perms_df["permission_id"].astype(str).tolist()

    n_total = len(user_ids) * len(resource_ids) * len(permission_ids)
    if n_total == 0:
        return []

    n_authorised_exact = 0
    for uid in user_ids:
        roles = user_roles.get(uid, set())
        for res_id in resource_ids:
            for perm_id in permission_ids:
                authorised = False
                for rid in roles:
                    for pa_perm, pa_res in role_perms.get(rid, []):
                        if pa_perm == perm_id:
                            if pa_res is None or pa_res == res_id:
                                authorised = True
                                break
                    if authorised:
                        break
                if authorised:
                    n_authorised_exact += 1

    issues: list[dict] = []
    if n_authorised_exact == 0:
        issues.append(_issue(
            severity="error",
            code=SINGLE_CLASS,
            file="role_permissions.csv",
            message=(
                "No authorised tuples found in the dataset. "
                "A classifier cannot be trained on single-class data "
                "(all negative). Check user_roles and role_permissions."
            ),
        ))
    elif n_authorised_exact == n_total:
        issues.append(_issue(
            severity="error",
            code=SINGLE_CLASS,
            file="role_permissions.csv",
            message=(
                "All tuples in the dataset are authorised. "
                "A classifier cannot be trained on single-class data "
                "(all positive). Add some unauthorised combinations."
            ),
        ))
    return issues
