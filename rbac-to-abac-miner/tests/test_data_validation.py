"""
tests/test_data_validation.py
------------------------------
Tests for the data validation library and the authorisation oracle.

Every expected value is independently derived — no values are copied
from any model's output (project rule RULE_12).

Owner : Shweta Suresh Kidile
Ref   : docs/modules/VALIDATION.md §1, §2
        data_engineering/documentation/test_cases.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from data_engineering.data_validation import (
    validate_dataset,
    brute_force_auth,
    verify_samples,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SCENARIOS_DIR = Path("data_engineering/test_scenarios")
SMALL_DIR = Path("data_engineering/sample_datasets/small")


def _load_scenario(filename: str) -> dict[str, pd.DataFrame]:
    """Load a test scenario JSON → dict of DataFrames (ignores _-prefixed keys)."""
    path = SCENARIOS_DIR / filename
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {
        k: pd.DataFrame(v)
        for k, v in raw.items()
        if not k.startswith("_")
    }


def _load_small() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in ["users", "roles", "permissions", "resources",
                 "user_roles", "role_permissions"]:
        tables[name] = pd.read_csv(SMALL_DIR / f"{name}.csv")
    return tables


def _codes(issues: list[dict]) -> set[str]:
    return {i["code"] for i in issues}


def _error_codes(issues: list[dict]) -> set[str]:
    return {i["code"] for i in issues if i["severity"] == "error"}


def _warning_codes(issues: list[dict]) -> set[str]:
    return {i["code"] for i in issues if i["severity"] == "warning"}


# ===========================================================================
# A. validate_dataset — structural checks
# ===========================================================================

class TestMissingFile:
    """TC-V-01: MISSING_FILE"""

    def test_missing_permissions_table(self) -> None:
        tables = _load_small()
        del tables["permissions"]
        issues = validate_dataset(tables)
        assert "MISSING_FILE" in _error_codes(issues)

    def test_missing_users_table(self) -> None:
        tables = _load_small()
        del tables["users"]
        issues = validate_dataset(tables)
        assert "MISSING_FILE" in _error_codes(issues)

    def test_empty_dict_returns_six_missing_file_errors(self) -> None:
        issues = validate_dataset({})
        missing_errors = [i for i in issues if i["code"] == "MISSING_FILE"]
        assert len(missing_errors) == 6, (
            f"Expected 6 MISSING_FILE errors, got {len(missing_errors)}"
        )


class TestEmptyFile:
    """TC-V-02: EMPTY_FILE"""

    def test_empty_users_table(self) -> None:
        tables = _load_scenario("empty_users.json")
        issues = validate_dataset(tables)
        assert "EMPTY_FILE" in _error_codes(issues)

    def test_empty_file_issue_references_correct_table(self) -> None:
        tables = _load_scenario("empty_users.json")
        issues = validate_dataset(tables)
        empty_issues = [i for i in issues if i["code"] == "EMPTY_FILE"]
        assert any("users" in i["file"] for i in empty_issues)


class TestMissingRequiredColumn:
    """TC-V-03: MISSING_COLUMN"""

    def test_users_missing_user_id_column(self) -> None:
        tables = _load_small()
        tables["users"] = tables["users"].drop(columns=["user_id"])
        issues = validate_dataset(tables)
        assert "MISSING_COLUMN" in _error_codes(issues)

    def test_missing_column_issue_names_correct_column(self) -> None:
        tables = _load_small()
        tables["roles"] = tables["roles"].drop(columns=["role_id"])
        issues = validate_dataset(tables)
        col_issues = [i for i in issues
                      if i["code"] == "MISSING_COLUMN" and i["column"] == "role_id"]
        assert col_issues, "Expected MISSING_COLUMN issue for 'role_id'"


class TestDuplicateKey:
    """TC-V-04: DUPLICATE_KEY"""

    def test_duplicate_user_id(self) -> None:
        tables = _load_scenario("duplicate_user_id.json")
        issues = validate_dataset(tables)
        assert "DUPLICATE_KEY" in _error_codes(issues)

    def test_duplicate_key_message_contains_value(self) -> None:
        tables = _load_scenario("duplicate_user_id.json")
        issues = validate_dataset(tables)
        dup = [i for i in issues if i["code"] == "DUPLICATE_KEY"]
        assert dup, "No DUPLICATE_KEY issues found"
        assert "U001" in dup[0]["message"]

    def test_valid_dataset_no_duplicate_key(self) -> None:
        tables = _load_small()
        issues = validate_dataset(tables)
        assert "DUPLICATE_KEY" not in _error_codes(issues)


class TestDuplicateRecord:
    """TC-V-05: DUPLICATE_RECORD"""

    def test_duplicate_ua_row(self) -> None:
        tables = _load_scenario("duplicate_record_ua.json")
        issues = validate_dataset(tables)
        assert "DUPLICATE_RECORD" in _warning_codes(issues)

    def test_duplicate_record_is_warning_not_error(self) -> None:
        tables = _load_scenario("duplicate_record_ua.json")
        issues = validate_dataset(tables)
        dup = [i for i in issues if i["code"] == "DUPLICATE_RECORD"]
        assert dup, "Expected DUPLICATE_RECORD warning"
        assert all(i["severity"] == "warning" for i in dup)


class TestDanglingReference:
    """TC-V-06: DANGLING_REFERENCE"""

    def test_dangling_role_in_user_roles(self) -> None:
        tables = _load_scenario("dangling_role_reference.json")
        issues = validate_dataset(tables)
        assert "DANGLING_REFERENCE" in _error_codes(issues)

    def test_dangling_reference_names_missing_value(self) -> None:
        tables = _load_scenario("dangling_role_reference.json")
        issues = validate_dataset(tables)
        dang = [i for i in issues if i["code"] == "DANGLING_REFERENCE"]
        assert dang
        assert "R99" in dang[0]["message"]

    def test_dangling_permission_in_role_permissions(self) -> None:
        tables = _load_small()
        # Inject a bad row into role_permissions
        bad_row = pd.DataFrame([{
            "role_id": "R01",
            "permission_id": "FAKE_PERM",
            "resource_id": "",
        }])
        tables["role_permissions"] = pd.concat(
            [tables["role_permissions"], bad_row], ignore_index=True
        )
        issues = validate_dataset(tables)
        assert "DANGLING_REFERENCE" in _error_codes(issues)


class TestMissingValue:
    """TC-V-07: MISSING_VALUE"""

    def test_missing_clearance_value(self) -> None:
        tables = _load_scenario("missing_value.json")
        issues = validate_dataset(tables)
        assert "MISSING_VALUE" in _warning_codes(issues)

    def test_missing_value_is_warning_not_error(self) -> None:
        tables = _load_scenario("missing_value.json")
        issues = validate_dataset(tables)
        mv = [i for i in issues if i["code"] == "MISSING_VALUE"]
        assert mv
        assert all(i["severity"] == "warning" for i in mv)

    def test_missing_value_identifies_column(self) -> None:
        tables = _load_scenario("missing_value.json")
        issues = validate_dataset(tables)
        mv = [i for i in issues if i["code"] == "MISSING_VALUE"]
        assert any(i["column"] == "clearance" for i in mv)


class TestInvalidType:
    """TC-V-08: INVALID_TYPE"""

    def test_non_numeric_seniority(self) -> None:
        tables = _load_scenario("invalid_type_seniority.json")
        issues = validate_dataset(tables)
        assert "INVALID_TYPE" in _error_codes(issues)

    def test_invalid_type_names_correct_column(self) -> None:
        tables = _load_scenario("invalid_type_seniority.json")
        issues = validate_dataset(tables)
        it = [i for i in issues if i["code"] == "INVALID_TYPE"]
        assert it
        assert it[0]["column"] == "seniority"


class TestInvalidValue:
    """TC-V-09: INVALID_VALUE"""

    def test_negative_seniority(self) -> None:
        tables = _load_scenario("invalid_value_negative.json")
        issues = validate_dataset(tables)
        assert "INVALID_VALUE" in _warning_codes(issues)

    def test_invalid_value_is_warning_not_error(self) -> None:
        tables = _load_scenario("invalid_value_negative.json")
        issues = validate_dataset(tables)
        iv = [i for i in issues if i["code"] == "INVALID_VALUE"]
        assert iv
        assert all(i["severity"] == "warning" for i in iv)


class TestUserWithoutRole:
    """TC-V-10: USER_WITHOUT_ROLE"""

    def test_user_no_roles_warning(self) -> None:
        tables = _load_scenario("user_no_roles.json")
        issues = validate_dataset(tables)
        assert "USER_WITHOUT_ROLE" in _warning_codes(issues)

    def test_user_without_role_is_warning_not_error(self) -> None:
        tables = _load_scenario("user_no_roles.json")
        issues = validate_dataset(tables)
        uw = [i for i in issues if i["code"] == "USER_WITHOUT_ROLE"]
        assert uw
        assert all(i["severity"] == "warning" for i in uw)

    def test_user_without_role_identifies_correct_user(self) -> None:
        tables = _load_scenario("user_no_roles.json")
        issues = validate_dataset(tables)
        uw = [i for i in issues if i["code"] == "USER_WITHOUT_ROLE"]
        assert any("U002" in i["message"] for i in uw)


class TestRoleWithoutPermission:
    """TC-V-11: ROLE_WITHOUT_PERMISSION"""

    def test_role_no_perms_warning(self) -> None:
        tables = _load_scenario("role_no_permissions.json")
        issues = validate_dataset(tables)
        assert "ROLE_WITHOUT_PERMISSION" in _warning_codes(issues)

    def test_role_without_permission_is_warning(self) -> None:
        tables = _load_scenario("role_no_permissions.json")
        issues = validate_dataset(tables)
        rw = [i for i in issues if i["code"] == "ROLE_WITHOUT_PERMISSION"]
        assert rw
        assert all(i["severity"] == "warning" for i in rw)

    def test_role_without_permission_names_correct_role(self) -> None:
        tables = _load_scenario("role_no_permissions.json")
        issues = validate_dataset(tables)
        rw = [i for i in issues if i["code"] == "ROLE_WITHOUT_PERMISSION"]
        assert any("R02" in i["message"] for i in rw)


class TestSingleClass:
    """TC-V-12 / TC-V-13: SINGLE_CLASS"""

    def test_all_authorised_triggers_single_class(self) -> None:
        tables = _load_scenario("all_authorised.json")
        issues = validate_dataset(tables)
        assert "SINGLE_CLASS" in _error_codes(issues)

    def test_none_authorised_triggers_single_class(self) -> None:
        tables = _load_scenario("none_authorised.json")
        issues = validate_dataset(tables)
        assert "SINGLE_CLASS" in _error_codes(issues)

    def test_single_class_is_error_not_warning(self) -> None:
        tables = _load_scenario("all_authorised.json")
        issues = validate_dataset(tables)
        sc = [i for i in issues if i["code"] == "SINGLE_CLASS"]
        assert sc
        assert all(i["severity"] == "error" for i in sc)


class TestValidDataset:
    """TC-V-14: A valid dataset produces no errors."""

    def test_valid_small_dataset_no_errors(self) -> None:
        tables = _load_small()
        issues = validate_dataset(tables)
        errors = [i for i in issues if i["severity"] == "error"]
        assert not errors, f"Unexpected errors on valid small dataset: {errors}"

    def test_unicode_dataset_no_errors(self) -> None:
        """TC-V-15: Unicode attribute values are handled gracefully."""
        tables = _load_scenario("unicode_names.json")
        issues = validate_dataset(tables)
        errors = [i for i in issues if i["severity"] == "error"]
        assert not errors, f"Unexpected errors on unicode dataset: {errors}"


class TestReturnShape:
    """Verify every returned dict has the exact ValidationIssue field set."""

    REQUIRED_KEYS = {"severity", "code", "file", "row", "column", "message"}

    def test_all_issues_have_required_keys(self) -> None:
        tables = _load_scenario("dangling_role_reference.json")
        issues = validate_dataset(tables)
        for iss in issues:
            missing = self.REQUIRED_KEYS - set(iss.keys())
            assert not missing, f"Issue is missing keys {missing}: {iss}"

    def test_severity_values_are_valid(self) -> None:
        tables = _load_scenario("dangling_role_reference.json")
        issues = validate_dataset(tables)
        for iss in issues:
            assert iss["severity"] in ("error", "warning"), (
                f"Invalid severity '{iss['severity']}'"
            )


# ===========================================================================
# B. brute_force_auth — oracle tests
# ===========================================================================

class TestOracleTiny3Users:
    """TC-O-01: 3-user hand example from test_cases.md §1.1"""

    def _make_tables(self) -> dict[str, pd.DataFrame]:
        users = pd.DataFrame([
            {"user_id": "U001", "department": "Finance", "seniority": 3, "clearance": "internal"},
            {"user_id": "U002", "department": "Finance", "seniority": 5, "clearance": "internal"},
            {"user_id": "U003", "department": "HR", "seniority": 7, "clearance": "public"},
        ])
        roles = pd.DataFrame([
            {"role_id": "R01", "role_name": "Finance_Analyst"},
            {"role_id": "R02", "role_name": "HR_Specialist"},
        ])
        permissions = pd.DataFrame([{"permission_id": "read"}])
        resources = pd.DataFrame([
            {"resource_id": "RES001", "department": "Finance", "sensitivity": "low", "type": "report"},
            {"resource_id": "RES002", "department": "Finance", "sensitivity": "medium", "type": "document"},
        ])
        ua = pd.DataFrame([
            {"user_id": "U001", "role_id": "R01"},
            {"user_id": "U002", "role_id": "R01"},
        ])
        pa = pd.DataFrame([
            {"role_id": "R01", "permission_id": "read", "resource_id": ""},
            {"role_id": "R02", "permission_id": "read", "resource_id": ""},
        ])
        return {
            "users": users, "roles": roles, "permissions": permissions,
            "resources": resources, "user_roles": ua, "role_permissions": pa,
        }

    def test_n_authorised_is_4(self) -> None:
        t = self._make_tables()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        assert int(auth["authorised"].sum()) == 4

    def test_n_unauthorised_is_2(self) -> None:
        t = self._make_tables()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        assert int((auth["authorised"] == 0).sum()) == 2

    def test_u003_never_authorised(self) -> None:
        t = self._make_tables()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        u3 = auth[auth["user_id"] == "U003"]
        assert (u3["authorised"] == 0).all(), "U003 should not be authorised"

    def test_output_columns(self) -> None:
        t = self._make_tables()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        assert list(auth.columns) == ["user_id", "resource_id", "permission", "authorised"]

    def test_total_tuples(self) -> None:
        """n_rows must equal n_users * n_resources * n_permissions = 3*2*1 = 6."""
        t = self._make_tables()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        assert len(auth) == 6


class TestOracleScopedPermission:
    """TC-O-02: Scoped permission — test_cases.md §1.2"""

    def test_scoped_write_permission(self) -> None:
        users = pd.DataFrame([
            {"user_id": "U001", "department": "Finance"},
            {"user_id": "U002", "department": "HR"},
        ])
        roles = pd.DataFrame([{"role_id": "R01", "role_name": "Analyst"}])
        permissions = pd.DataFrame([{"permission_id": "write"}])
        resources = pd.DataFrame([
            {"resource_id": "RES001", "department": "Finance"},
            {"resource_id": "RES002", "department": "HR"},
        ])
        ua = pd.DataFrame([
            {"user_id": "U001", "role_id": "R01"},
            {"user_id": "U002", "role_id": "R01"},
        ])
        # write scoped to RES001 only
        pa = pd.DataFrame([
            {"role_id": "R01", "permission_id": "write", "resource_id": "RES001"}
        ])
        auth = brute_force_auth(users, roles, permissions, ua, pa, resources)
        assert int(auth["authorised"].sum()) == 2
        assert int((auth["authorised"] == 0).sum()) == 2
        # Specifically: U001/RES002 and U002/RES002 should be 0
        u1r2 = auth[(auth["user_id"] == "U001") & (auth["resource_id"] == "RES002")]
        assert int(u1r2["authorised"].iloc[0]) == 0
        u2r2 = auth[(auth["user_id"] == "U002") & (auth["resource_id"] == "RES002")]
        assert int(u2r2["authorised"].iloc[0]) == 0


class TestOracleMultiRole:
    """TC-O-03: Multi-role user — test_cases.md §1.3"""

    def test_multi_role_user_all_authorised(self) -> None:
        users = pd.DataFrame([{"user_id": "U001", "department": "Finance"}])
        roles = pd.DataFrame([
            {"role_id": "R01", "role_name": "Analyst"},
            {"role_id": "R02", "role_name": "Writer"},
        ])
        permissions = pd.DataFrame([
            {"permission_id": "read"},
            {"permission_id": "write"},
        ])
        resources = pd.DataFrame([{"resource_id": "RES001", "department": "Finance"}])
        ua = pd.DataFrame([
            {"user_id": "U001", "role_id": "R01"},
            {"user_id": "U001", "role_id": "R02"},
        ])
        pa = pd.DataFrame([
            {"role_id": "R01", "permission_id": "read", "resource_id": ""},
            {"role_id": "R02", "permission_id": "write", "resource_id": "RES001"},
        ])
        auth = brute_force_auth(users, roles, permissions, ua, pa, resources)
        assert int(auth["authorised"].sum()) == 2
        assert len(auth) == 2


class TestOracleSortedOutput:
    """TC-O-05: Output must be sorted by (user_id, resource_id, permission)."""

    def test_sorted_output(self) -> None:
        tables = _load_small()
        auth = brute_force_auth(
            tables["users"], tables["roles"], tables["permissions"],
            tables["user_roles"], tables["role_permissions"], tables["resources"]
        )
        expected_order = auth.sort_values(
            ["user_id", "resource_id", "permission"]
        ).reset_index(drop=True)
        pd.testing.assert_frame_equal(auth.reset_index(drop=True), expected_order)


class TestOracleFullCoverage:
    """TC-O-07: Oracle covers all N×R×P tuples."""

    def test_full_coverage_small(self) -> None:
        tables = _load_small()
        auth = brute_force_auth(
            tables["users"], tables["roles"], tables["permissions"],
            tables["user_roles"], tables["role_permissions"], tables["resources"]
        )
        n_users = len(tables["users"])
        n_resources = len(tables["resources"])
        n_perms = len(tables["permissions"])
        expected = n_users * n_resources * n_perms
        assert len(auth) == expected, (
            f"Expected {expected} rows ({n_users}×{n_resources}×{n_perms}), "
            f"got {len(auth)}"
        )


# ===========================================================================
# C. verify_samples tests
# ===========================================================================

class TestVerifySamples:
    """TC-I-02 / TC-I-03 / TC-I-04: verify_samples"""

    def _make_auth(self) -> pd.DataFrame:
        """Tiny auth matrix: U001 read RES001 = authorised, U002 = not."""
        return pd.DataFrame([
            {"user_id": "U001", "resource_id": "RES001", "permission": "read", "authorised": 1},
            {"user_id": "U002", "resource_id": "RES001", "permission": "read", "authorised": 0},
        ])

    def test_correct_samples_no_issues(self) -> None:
        """TC-I-02: Correct samples pass with no issues."""
        auth = self._make_auth()
        samples = pd.DataFrame([
            {"user_id": "U001", "resource_id": "RES001", "permission": "read", "authorised": 1},
            {"user_id": "U002", "resource_id": "RES001", "permission": "read", "authorised": 0},
        ])
        issues = verify_samples(auth, samples)
        assert not issues, f"Expected no issues but got: {issues}"

    def test_wrong_positive_label(self) -> None:
        """TC-I-03: A sample labelled 1 that is 0 in auth → error."""
        auth = self._make_auth()
        samples = pd.DataFrame([
            {"user_id": "U002", "resource_id": "RES001", "permission": "read", "authorised": 1},
        ])
        issues = verify_samples(auth, samples)
        assert any(i["code"] == "SAMPLE_LABEL_MISMATCH" for i in issues)

    def test_wrong_negative_label(self) -> None:
        """TC-I-04: A sample labelled 0 that is 1 in auth → error."""
        auth = self._make_auth()
        samples = pd.DataFrame([
            {"user_id": "U001", "resource_id": "RES001", "permission": "read", "authorised": 0},
        ])
        issues = verify_samples(auth, samples)
        assert any(i["code"] == "SAMPLE_LABEL_MISMATCH" for i in issues)

    def test_duplicate_sample_rows_warning(self) -> None:
        auth = self._make_auth()
        samples = pd.DataFrame([
            {"user_id": "U001", "resource_id": "RES001", "permission": "read", "authorised": 1},
            {"user_id": "U001", "resource_id": "RES001", "permission": "read", "authorised": 1},
        ])
        issues = verify_samples(auth, samples)
        assert any(i["code"] == "DUPLICATE_RECORD" for i in issues)

    def test_missing_authorised_column(self) -> None:
        auth = self._make_auth()
        samples = pd.DataFrame([
            {"user_id": "U001", "resource_id": "RES001", "permission": "read"},
        ])
        issues = verify_samples(auth, samples)
        assert any(i["code"] == "MISSING_COLUMN" for i in issues)
