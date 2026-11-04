"""RBAC dataset loader.

Loads the six required RBAC tables (users, roles, permissions, user_roles,
role_permissions, resources) from either CSV files or a single JSON file.

Decision D-001: permission is an action; role_permissions may optionally carry
a resource_id column to scope the permission (empty/absent = all resources).
"""
from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# Required columns per table
REQUIRED_COLUMNS: Dict[str, List[str]] = {
    "users": ["user_id"],
    "roles": ["role_id"],
    "permissions": ["permission_id"],
    "user_roles": ["user_id", "role_id"],
    "role_permissions": ["role_id", "permission_id"],
    "resources": ["resource_id"],
}

TABLE_NAMES = list(REQUIRED_COLUMNS.keys())


@dataclass
class RBACDataset:
    """Holds the six raw RBAC tables as DataFrames.

    Attributes:
        users: DataFrame with user_id + attribute columns.
        roles: DataFrame with role_id (and optional role_name).
        permissions: DataFrame with permission_id.
        user_roles: DataFrame with user_id, role_id (UA relation).
        role_permissions: DataFrame with role_id, permission_id, optional resource_id (PA relation).
        resources: DataFrame with resource_id + attribute columns.
        user_attribute_columns: Names of user attribute columns (excluding user_id).
        resource_attribute_columns: Names of resource attribute columns (excluding resource_id).
        dataset_name: Human-readable name of the dataset.
        file_format: "csv" or "json".
    """

    users: pd.DataFrame
    roles: pd.DataFrame
    permissions: pd.DataFrame
    user_roles: pd.DataFrame
    role_permissions: pd.DataFrame
    resources: pd.DataFrame
    user_attribute_columns: List[str] = field(default_factory=list)
    resource_attribute_columns: List[str] = field(default_factory=list)
    dataset_name: str = ""
    file_format: str = "csv"


def _read_csv_bytes(data: bytes, table_name: str) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame.

    Args:
        data: Raw CSV bytes.
        table_name: Table name for error messages.

    Returns:
        DataFrame with snake_case column names.

    Raises:
        ValueError: If the CSV cannot be parsed.
    """
    try:
        df = pd.read_csv(io.BytesIO(data), dtype=str)
    except Exception as exc:
        raise ValueError(f"Cannot parse CSV for table '{table_name}': {exc}") from exc
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _read_json_table(data: bytes, table_name: str) -> pd.DataFrame:
    """Parse a JSON object containing one array-of-records per table name.

    Args:
        data: Raw JSON bytes (the full multi-table object).
        table_name: Key to extract from the JSON object.

    Returns:
        DataFrame for the requested table.

    Raises:
        ValueError: If the table is missing or the JSON is malformed.
    """
    try:
        obj = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Cannot parse JSON: {exc}") from exc
    if table_name not in obj:
        raise ValueError(f"JSON object is missing key '{table_name}'")
    records = obj[table_name]
    if not isinstance(records, list):
        raise ValueError(f"JSON key '{table_name}' must be an array of records")
    df = pd.DataFrame(records).astype(str)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _validate_required_columns(df: pd.DataFrame, table_name: str) -> None:
    """Check that all required columns are present.

    Args:
        df: The table to validate.
        table_name: Used in the error message.

    Raises:
        ValueError: If required columns are absent.
    """
    required = REQUIRED_COLUMNS[table_name]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Table '{table_name}' is missing required columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )


def _infer_attribute_columns(
    df: pd.DataFrame,
    id_column: str,
    explicit: Optional[List[str]],
    table_name: str,
) -> List[str]:
    """Return the list of attribute columns for a table.

    If explicit is provided and non-empty, validate the columns exist and return them.
    Otherwise return all columns except the id column.

    Args:
        df: The table DataFrame.
        id_column: Name of the primary key column.
        explicit: User-supplied list of attribute column names, or None.
        table_name: Used in error messages.

    Returns:
        List of attribute column names.

    Raises:
        ValueError: If explicitly listed columns are not present.
    """
    if explicit:
        missing = [c for c in explicit if c not in df.columns]
        if missing:
            raise ValueError(
                f"Table '{table_name}': specified attribute columns not found: {missing}"
            )
        return list(explicit)
    return [c for c in df.columns if c != id_column]


def load_rbac_dataset(
    files: Dict[str, bytes],
    fmt: str = "csv",
    dataset_name: str = "",
    user_attribute_columns: Optional[List[str]] = None,
    resource_attribute_columns: Optional[List[str]] = None,
) -> RBACDataset:
    """Load the six RBAC tables from byte content.

    Args:
        files: Mapping from table name to raw file bytes.
                Keys must be a subset of TABLE_NAMES.
        fmt: "csv" or "json". For "json", all tables are in a single file;
             pass the same bytes under any of the table-name keys (or under
             the key "json").
        dataset_name: Human-readable name stored in the result.
        user_attribute_columns: If provided, only these columns (besides
            user_id) are treated as user attributes. Otherwise all non-id
            columns are used.
        resource_attribute_columns: Same for resources.

    Returns:
        RBACDataset with all six tables populated.

    Raises:
        ValueError: If required tables or columns are missing or cannot be parsed.
    """
    fmt = fmt.lower()
    if fmt not in ("csv", "json"):
        raise ValueError(f"Unsupported file format: '{fmt}'. Use 'csv' or 'json'.")

    tables: Dict[str, pd.DataFrame] = {}

    if fmt == "csv":
        for table_name in TABLE_NAMES:
            if table_name not in files:
                raise ValueError(f"Missing required file for table '{table_name}'.")
            df = _read_csv_bytes(files[table_name], table_name)
            _validate_required_columns(df, table_name)
            tables[table_name] = df
    else:
        # JSON: all tables in a single payload
        # Accept the payload under any known key or under "json"
        payload: Optional[bytes] = None
        for key in list(TABLE_NAMES) + ["json"]:
            if key in files:
                payload = files[key]
                break
        if payload is None:
            raise ValueError(
                "For JSON format, pass the payload under any of the table-name keys."
            )
        for table_name in TABLE_NAMES:
            df = _read_json_table(payload, table_name)
            _validate_required_columns(df, table_name)
            tables[table_name] = df

    # Normalise string columns: strip whitespace, keep as str
    for name, df in tables.items():
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].str.strip()
        tables[name] = df

    user_attrs = _infer_attribute_columns(
        tables["users"], "user_id", user_attribute_columns, "users"
    )
    resource_attrs = _infer_attribute_columns(
        tables["resources"], "resource_id", resource_attribute_columns, "resources"
    )

    logger.info(
        "Loaded dataset '%s': %d users, %d roles, %d permissions, %d resources",
        dataset_name,
        len(tables["users"]),
        len(tables["roles"]),
        len(tables["permissions"]),
        len(tables["resources"]),
    )

    return RBACDataset(
        users=tables["users"],
        roles=tables["roles"],
        permissions=tables["permissions"],
        user_roles=tables["user_roles"],
        role_permissions=tables["role_permissions"],
        resources=tables["resources"],
        user_attribute_columns=user_attrs,
        resource_attribute_columns=resource_attrs,
        dataset_name=dataset_name,
        file_format=fmt,
    )
