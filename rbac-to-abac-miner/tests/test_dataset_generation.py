"""
tests/test_dataset_generation.py
---------------------------------
Tests for data_engineering/sample_datasets/generate_sample.py.

All expected values are from hand-knowledge of the generator spec
(never copied from model output).

Owner : Shweta Suresh Kidile
Ref   : docs/team_guides/SHWETA_GUIDE.md Task 2
        data_engineering/documentation/test_cases.md §5
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Import the generator
# ---------------------------------------------------------------------------
from data_engineering.sample_datasets.generate_sample import generate_dataset

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
REQUIRED_FILES = [
    "users.csv",
    "roles.csv",
    "permissions.csv",
    "resources.csv",
    "user_roles.csv",
    "role_permissions.csv",
    "dataset.json",
]

REQUIRED_COLUMNS = {
    "users":            ["user_id", "department", "seniority", "clearance"],
    "roles":            ["role_id", "role_name"],
    "permissions":      ["permission_id"],
    "resources":        ["resource_id", "department", "sensitivity", "type"],
    "user_roles":       ["user_id", "role_id"],
    "role_permissions": ["role_id", "permission_id"],
}


@pytest.fixture(scope="module")
def small_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the small dataset once for all tests in this module."""
    out = tmp_path_factory.mktemp("small_42")
    generate_dataset(size="small", seed=42, out_dir=str(out))
    return out


@pytest.fixture(scope="module")
def medium_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the medium dataset once."""
    out = tmp_path_factory.mktemp("medium_42")
    generate_dataset(size="medium", seed=42, out_dir=str(out))
    return out


# ---------------------------------------------------------------------------
# TC-G-05: All 6 CSV files generated
# ---------------------------------------------------------------------------
class TestAllFilesGenerated:
    def test_small_has_all_files(self, small_dir: Path) -> None:
        """TC-G-05: Every expected file is present in the small output dir."""
        for fname in REQUIRED_FILES:
            assert (small_dir / fname).exists(), f"Missing file: {fname}"

    def test_medium_has_all_files(self, medium_dir: Path) -> None:
        for fname in REQUIRED_FILES:
            assert (medium_dir / fname).exists(), f"Missing file: {fname}"


# ---------------------------------------------------------------------------
# TC-G-07: Required columns present
# ---------------------------------------------------------------------------
class TestRequiredColumns:
    @pytest.mark.parametrize("table,cols", REQUIRED_COLUMNS.items())
    def test_small_columns(self, small_dir: Path, table: str, cols: list) -> None:
        """TC-G-07: Each CSV has the expected columns per DATA_PIPELINE.md §1."""
        df = pd.read_csv(small_dir / f"{table}.csv")
        for col in cols:
            assert col in df.columns, (
                f"table '{table}' missing required column '{col}'"
            )

    @pytest.mark.parametrize("table,cols", REQUIRED_COLUMNS.items())
    def test_medium_columns(self, medium_dir: Path, table: str, cols: list) -> None:
        df = pd.read_csv(medium_dir / f"{table}.csv")
        for col in cols:
            assert col in df.columns, (
                f"table '{table}' missing required column '{col}'"
            )


# ---------------------------------------------------------------------------
# TC-G-03: Small dataset has correct shape
# ---------------------------------------------------------------------------
class TestSmallDatasetShape:
    def test_n_users(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "users.csv")
        assert len(df) == 12, f"Expected 12 users, got {len(df)}"

    def test_n_roles(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "roles.csv")
        assert len(df) == 4, f"Expected 4 roles, got {len(df)}"

    def test_n_permissions(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "permissions.csv")
        assert len(df) == 3, f"Expected 3 permissions, got {len(df)}"

    def test_n_resources(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "resources.csv")
        assert len(df) == 8, f"Expected 8 resources, got {len(df)}"


# ---------------------------------------------------------------------------
# TC-G-04: Medium dataset has correct shape
# ---------------------------------------------------------------------------
class TestMediumDatasetShape:
    def test_n_users(self, medium_dir: Path) -> None:
        df = pd.read_csv(medium_dir / "users.csv")
        assert len(df) == 200

    def test_n_roles(self, medium_dir: Path) -> None:
        df = pd.read_csv(medium_dir / "roles.csv")
        assert len(df) == 8

    def test_n_permissions(self, medium_dir: Path) -> None:
        df = pd.read_csv(medium_dir / "permissions.csv")
        assert len(df) == 5

    def test_n_resources(self, medium_dir: Path) -> None:
        df = pd.read_csv(medium_dir / "resources.csv")
        assert len(df) == 100


# ---------------------------------------------------------------------------
# TC-G-01: Same seed → identical files
# ---------------------------------------------------------------------------
class TestDeterminism:
    def test_same_seed_gives_identical_users(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """TC-G-01: Running with seed=42 twice gives byte-identical users.csv."""
        out_a = tmp_path_factory.mktemp("det_a")
        out_b = tmp_path_factory.mktemp("det_b")
        generate_dataset("small", seed=42, out_dir=str(out_a))
        generate_dataset("small", seed=42, out_dir=str(out_b))
        for fname in REQUIRED_FILES:
            content_a = (out_a / fname).read_bytes()
            content_b = (out_b / fname).read_bytes()
            assert content_a == content_b, (
                f"File '{fname}' differs between two runs with seed=42"
            )

    def test_same_seed_gives_identical_json(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        out_a = tmp_path_factory.mktemp("det_json_a")
        out_b = tmp_path_factory.mktemp("det_json_b")
        generate_dataset("small", seed=42, out_dir=str(out_a))
        generate_dataset("small", seed=42, out_dir=str(out_b))
        data_a = json.loads((out_a / "dataset.json").read_text(encoding="utf-8"))
        data_b = json.loads((out_b / "dataset.json").read_text(encoding="utf-8"))
        assert data_a == data_b


# ---------------------------------------------------------------------------
# TC-G-02: Different seeds produce different data
# ---------------------------------------------------------------------------
class TestDifferentSeeds:
    def test_different_seeds_differ(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """TC-G-02: Seed 42 and seed 99 should produce different user data."""
        out_42 = tmp_path_factory.mktemp("seed42")
        out_99 = tmp_path_factory.mktemp("seed99")
        generate_dataset("small", seed=42, out_dir=str(out_42))
        generate_dataset("small", seed=99, out_dir=str(out_99))
        df_42 = pd.read_csv(out_42 / "users.csv")
        df_99 = pd.read_csv(out_99 / "users.csv")
        # The shapes should be the same (same size) but the data may differ
        # (department / clearance assignments are random)
        assert not df_42.equals(df_99), (
            "Users with seed=42 and seed=99 are identical — RNG is not varying"
        )


# ---------------------------------------------------------------------------
# TC-G-06: JSON has same data as CSVs
# ---------------------------------------------------------------------------
class TestJsonMatchesCsv:
    def test_json_record_counts_match_csvs(self, small_dir: Path) -> None:
        """TC-G-06: dataset.json has the same row count as each CSV."""
        with open(small_dir / "dataset.json", encoding="utf-8") as fh:
            data = json.load(fh)
        for table in [
            "users", "roles", "permissions", "resources",
            "user_roles", "role_permissions",
        ]:
            csv_len = len(pd.read_csv(small_dir / f"{table}.csv"))
            json_len = len(data[table])
            assert csv_len == json_len, (
                f"table '{table}': CSV has {csv_len} rows but JSON has {json_len}"
            )

    def test_json_users_match_csv_users(self, small_dir: Path) -> None:
        """JSON users table has the same user_ids as users.csv."""
        with open(small_dir / "dataset.json", encoding="utf-8") as fh:
            data = json.load(fh)
        csv_ids = set(pd.read_csv(small_dir / "users.csv")["user_id"].astype(str))
        json_ids = {str(r["user_id"]) for r in data["users"]}
        assert csv_ids == json_ids


# ---------------------------------------------------------------------------
# TC-G-08: Unknown size raises ValueError
# ---------------------------------------------------------------------------
class TestErrorHandling:
    def test_unknown_size_raises(self, tmp_path: Path) -> None:
        """TC-G-08: An unrecognised size string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown size"):
            generate_dataset(size="xlarge", seed=42, out_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# Data integrity checks
# ---------------------------------------------------------------------------
class TestDataIntegrity:
    def test_user_ids_unique(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "users.csv")
        assert df["user_id"].nunique() == len(df), "user_ids are not unique"

    def test_role_ids_unique(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "roles.csv")
        assert df["role_id"].nunique() == len(df), "role_ids are not unique"

    def test_resource_ids_unique(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "resources.csv")
        assert df["resource_id"].nunique() == len(df), "resource_ids are not unique"

    def test_user_roles_references_valid_users(self, small_dir: Path) -> None:
        users = set(pd.read_csv(small_dir / "users.csv")["user_id"].astype(str))
        ur = pd.read_csv(small_dir / "user_roles.csv")
        for uid in ur["user_id"].astype(str):
            assert uid in users, f"user_roles references unknown user_id '{uid}'"

    def test_user_roles_references_valid_roles(self, small_dir: Path) -> None:
        roles = set(pd.read_csv(small_dir / "roles.csv")["role_id"].astype(str))
        ur = pd.read_csv(small_dir / "user_roles.csv")
        for rid in ur["role_id"].astype(str):
            assert rid in roles, f"user_roles references unknown role_id '{rid}'"

    def test_seniority_positive(self, small_dir: Path) -> None:
        df = pd.read_csv(small_dir / "users.csv")
        assert (df["seniority"] > 0).all(), "All seniority values should be positive"

    def test_both_auth_classes_present(self, small_dir: Path) -> None:
        """The small dataset should have both authorised and non-authorised tuples."""
        import pandas as pd
        from data_engineering.data_validation.oracle import brute_force_auth
        tables = {
            name: pd.read_csv(small_dir / f"{name}.csv")
            for name in ["users", "roles", "permissions", "resources",
                         "user_roles", "role_permissions"]
        }
        auth = brute_force_auth(
            tables["users"], tables["roles"], tables["permissions"],
            tables["user_roles"], tables["role_permissions"], tables["resources"]
        )
        assert auth["authorised"].sum() > 0, "No authorised tuples found"
        assert (auth["authorised"] == 0).sum() > 0, "No unauthorised tuples found"
