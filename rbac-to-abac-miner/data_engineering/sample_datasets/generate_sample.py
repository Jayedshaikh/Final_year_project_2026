"""
Seeded synthetic RBAC dataset generator.

Produces six CSV files (users, roles, permissions, resources,
user_roles, role_permissions) and an equivalent JSON file.

Usage:
    python data_engineering/sample_datasets/generate_sample.py \
        --size small --seed 42 --out data_engineering/sample_datasets/small

Sizes:
    small  : ~12 users, 4 roles, 3 permissions, 8 resources  (unit tests)
    medium : ~200 users, 8 roles, 5 permissions, 100 resources (demo)

Planted pattern (documented in README.md, never fed to the ML pipeline):
    Each department maps to a primary role that grants the main permission for
    resources in the same department, with a configurable noise level (~10 %).
    This ensures the Decision Tree has real structure to learn.

Owner : Shweta Suresh Kidile
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# -------------------------------------------------------------------------
# Size configuration
# -------------------------------------------------------------------------
SIZE_CONFIG: dict[str, dict[str, Any]] = {
    "small": {
        "n_users": 12,
        "n_roles": 4,
        "n_permissions": 3,
        "n_resources": 8,
        "noise_prob": 0.10,  # probability of giving a user an off-pattern role
    },
    "medium": {
        "n_users": 200,
        "n_roles": 8,
        "n_permissions": 5,
        "n_resources": 100,
        "noise_prob": 0.08,
    },
}

# Fixed attribute domain values — must stay consistent across sizes
DEPARTMENTS = ["Finance", "HR", "Engineering", "Legal", "Operations",
               "Marketing", "Security", "IT"]
SENIORITY_RANGE = (1, 15)          # years, inclusive
CLEARANCES = ["public", "internal", "confidential", "secret"]
RESOURCE_TYPES = ["report", "document", "database", "application", "portal"]
SENSITIVITIES = ["low", "medium", "high"]
PERMISSION_ACTIONS = ["read", "write", "delete", "admin", "execute"]


def generate_dataset(size: str, seed: int, out_dir: str) -> None:
    """Generate all six RBAC tables and write CSV + JSON to *out_dir*.

    Parameters
    ----------
    size:    "small" or "medium"
    seed:    integer RNG seed — same seed → byte-identical output
    out_dir: target directory (created if it does not exist)

    Raises
    ------
    ValueError  if *size* is not recognised
    """
    if size not in SIZE_CONFIG:
        raise ValueError(
            f"Unknown size '{size}'. Choose from: {list(SIZE_CONFIG.keys())}"
        )

    cfg = SIZE_CONFIG[size]
    rng = np.random.default_rng(seed)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    n_users = cfg["n_users"]
    n_roles = cfg["n_roles"]
    n_permissions = cfg["n_permissions"]
    n_resources = cfg["n_resources"]
    noise_prob = cfg["noise_prob"]

    # -- 1. Roles ----------------------------------------------------------
    role_names_base = [
        "Finance_Analyst", "HR_Specialist", "Engineering_Lead", "Legal_Advisor",
        "Operations_Manager", "Marketing_Executive", "Security_Officer", "IT_Admin",
    ]
    role_ids = [f"R{str(i + 1).zfill(2)}" for i in range(n_roles)]
    role_names = role_names_base[:n_roles]
    roles_df = pd.DataFrame({"role_id": role_ids, "role_name": role_names})

    # -- 2. Permissions ----------------------------------------------------
    perm_actions = PERMISSION_ACTIONS[:n_permissions]
    permissions_df = pd.DataFrame({"permission_id": perm_actions})

    # -- 3. Departments aligned with roles (planted pattern) ---------------
    # role i "belongs to" department i — this is the planted pattern
    role_departments = DEPARTMENTS[:n_roles]           # R01 → Finance, R02 → HR, …
    # map role_id → department for internal use (NOT written to CSV)
    role_dept_map: dict[str, str] = dict(zip(role_ids, role_departments))

    # -- 4. Users ----------------------------------------------------------
    user_ids = [f"U{str(i + 1).zfill(3)}" for i in range(n_users)]

    # Assign each user a "home" department (determines primary role)
    user_depts = rng.choice(DEPARTMENTS[:n_roles], size=n_users).tolist()
    user_seniority = rng.integers(
        SENIORITY_RANGE[0], SENIORITY_RANGE[1] + 1, size=n_users
    ).tolist()
    user_clearance = rng.choice(CLEARANCES, size=n_users).tolist()

    users_df = pd.DataFrame({
        "user_id": user_ids,
        "department": user_depts,
        "seniority": user_seniority,
        "clearance": user_clearance,
    })

    # -- 5. Resources ------------------------------------------------------
    resource_ids = [f"RES{str(i + 1).zfill(3)}" for i in range(n_resources)]
    # Assign each resource a department, sensitivity and type
    res_depts = rng.choice(DEPARTMENTS[:n_roles], size=n_resources).tolist()
    res_sensitivities = rng.choice(SENSITIVITIES, size=n_resources).tolist()
    res_types = rng.choice(RESOURCE_TYPES, size=n_resources).tolist()

    resources_df = pd.DataFrame({
        "resource_id": resource_ids,
        "department": res_depts,
        "sensitivity": res_sensitivities,
        "type": res_types,
    })

    # -- 6. User-Roles (UA) — planted pattern with noise ------------------
    # Primary assignment: each user gets the role matching their department
    dept_to_role: dict[str, str] = {dept: rid
                                     for dept, rid in zip(role_departments, role_ids)}

    ua_rows: list[dict[str, str]] = []
    for uid, dept in zip(user_ids, user_depts):
        primary_role = dept_to_role[dept]
        ua_rows.append({"user_id": uid, "role_id": primary_role})

        # Noise: ~10 % of users get a second, randomly chosen role
        if rng.random() < noise_prob:
            noise_role = rng.choice(role_ids)
            if noise_role != primary_role:
                ua_rows.append({"user_id": uid, "role_id": noise_role})

    user_roles_df = pd.DataFrame(ua_rows).drop_duplicates()

    # -- 7. Role-Permissions (PA) -----------------------------------------
    # Planted pattern:
    #   - Every role gets "read" on all resources (no resource scope)
    #   - Roles R01 and R02 additionally get "write" on resources in their dept
    #   - The first role (R01) gets "delete" on nothing (for sparsity)
    #   - Additional permissions assigned with probability 0.3 for variety
    pa_rows: list[dict[str, str]] = []

    for rid in role_ids:
        # Universal read — blank resource_id = all resources (D-001 default)
        pa_rows.append({"role_id": rid, "permission_id": "read", "resource_id": ""})

        # Department-scoped write for roles that have "write" permission available
        if "write" in perm_actions:
            dept = role_dept_map[rid]
            dept_resources = [
                r for r, d in zip(resource_ids, res_depts) if d == dept
            ]
            for res in dept_resources:
                pa_rows.append({
                    "role_id": rid,
                    "permission_id": "write",
                    "resource_id": res,
                })

        # Randomly assign extra permissions (for learnable variety)
        extra_perms = [p for p in perm_actions if p not in ("read", "write")]
        for perm in extra_perms:
            if rng.random() < 0.25:
                pa_rows.append({
                    "role_id": rid,
                    "permission_id": perm,
                    "resource_id": "",
                })

    role_permissions_df = pd.DataFrame(pa_rows).drop_duplicates()

    # -- 8. Write CSV files -----------------------------------------------
    tables: dict[str, pd.DataFrame] = {
        "users": users_df,
        "roles": roles_df,
        "permissions": permissions_df,
        "resources": resources_df,
        "user_roles": user_roles_df,
        "role_permissions": role_permissions_df,
    }

    for name, df in tables.items():
        csv_path = out_path / f"{name}.csv"
        df.to_csv(csv_path, index=False)

    # -- 9. Write combined JSON -------------------------------------------
    json_data: dict[str, list[dict]] = {
        name: df.to_dict(orient="records") for name, df in tables.items()
    }
    json_path = out_path / "dataset.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(json_data, fh, indent=2, ensure_ascii=False)

    # -- 10. Print summary ------------------------------------------------
    print(f"[generate_sample] size={size} seed={seed} out={out_dir}")
    for name, df in tables.items():
        print(f"  {name}.csv : {len(df)} rows")
    print(f"  dataset.json : {sum(len(v) for v in json_data.values())} total records")


# -------------------------------------------------------------------------
# CLI entry-point
# -------------------------------------------------------------------------
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic RBAC datasets for the RBAC-to-ABAC miner."
    )
    parser.add_argument(
        "--size",
        choices=list(SIZE_CONFIG.keys()),
        default="small",
        help="Dataset size: small (~12 users) or medium (~200 users)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory (created if it does not exist)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    generate_dataset(size=args.size, seed=args.seed, out_dir=args.out)
