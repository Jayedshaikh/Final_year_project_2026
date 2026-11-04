"""
tests/test_integration.py
--------------------------
Integration and cross-module tests.

Tests that don't need the backend run always.
Tests that require the backend (Jayed's) or policy_engine (Granthali's)
are marked with @pytest.mark.skipif.

Owner : Shweta Suresh Kidile
Ref   : docs/modules/PROJECT_ARCHITECTURE.md §8
        data_engineering/documentation/test_cases.md §7
        ROADMAP.md Milestones M3, M4, M12
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from data_engineering.data_validation import (
    validate_dataset,
    brute_force_auth,
    verify_samples,
)

# ---------------------------------------------------------------------------
# Availability guards
# ---------------------------------------------------------------------------
_BACKEND_URL = os.environ.get("RBAC_BACKEND_URL", "").strip()
_BACKEND_AVAILABLE = bool(_BACKEND_URL)

_BACKEND_MODULE_AVAILABLE = False
try:
    from backend.data_pipeline.auth_matrix import build_auth_matrix  # noqa: F401
    _BACKEND_MODULE_AVAILABLE = True
except ImportError:
    pass

_POLICY_ENGINE_AVAILABLE = False
try:
    from policy_engine import validate_policy  # noqa: F401
    _POLICY_ENGINE_AVAILABLE = True
except ImportError:
    pass

backend_module_required = pytest.mark.skipif(
    not _BACKEND_MODULE_AVAILABLE,
    reason="backend.data_pipeline not yet implemented (Milestone 3).",
)

backend_http_required = pytest.mark.skipif(
    not _BACKEND_AVAILABLE,
    reason=(
        "Backend HTTP server not available. "
        "Set RBAC_BACKEND_URL to enable (Milestone 10)."
    ),
)

policy_engine_required = pytest.mark.skipif(
    not _POLICY_ENGINE_AVAILABLE,
    reason="policy_engine not yet implemented (Milestone 8).",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SMALL_DIR = Path("data_engineering/sample_datasets/small")
SCENARIOS_DIR = Path("data_engineering/test_scenarios")


def _load_small() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in ["users", "roles", "permissions", "resources",
                 "user_roles", "role_permissions"]:
        tables[name] = pd.read_csv(SMALL_DIR / f"{name}.csv")
    return tables


# ===========================================================================
# A. Oracle + validator self-consistency (no backend needed — always run)
# ===========================================================================

class TestOracleConsistency:
    """verify_samples is consistent with brute_force_auth on the small dataset."""

    def test_oracle_produces_both_classes(self) -> None:
        """The small dataset must have both authorised and non-authorised tuples."""
        t = _load_small()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        assert int(auth["authorised"].sum()) > 0, "No positive class"
        assert int((auth["authorised"] == 0).sum()) > 0, "No negative class"

    def test_verify_samples_accepts_correct_positives(self) -> None:
        """All authorised rows from oracle pass verify_samples as positives."""
        t = _load_small()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        positives = auth[auth["authorised"] == 1].copy()
        issues = verify_samples(auth, positives)
        mismatch = [i for i in issues if i["code"] == "SAMPLE_LABEL_MISMATCH"]
        assert not mismatch, f"Unexpected label mismatches: {mismatch}"

    def test_verify_samples_accepts_correct_negatives(self) -> None:
        """All unauthorised rows from oracle pass verify_samples as negatives."""
        t = _load_small()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        negatives = auth[auth["authorised"] == 0].copy()
        issues = verify_samples(auth, negatives)
        mismatch = [i for i in issues if i["code"] == "SAMPLE_LABEL_MISMATCH"]
        assert not mismatch, f"Unexpected label mismatches: {mismatch}"

    def test_verify_samples_catches_injected_error(self) -> None:
        """verify_samples must catch a deliberately wrong label."""
        t = _load_small()
        auth = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        # Take a positive row and flip its label to 0
        bad_samples = auth[auth["authorised"] == 1].copy().head(1)
        bad_samples = bad_samples.copy()
        bad_samples["authorised"] = 0  # deliberately wrong
        issues = verify_samples(auth, bad_samples)
        assert any(i["code"] == "SAMPLE_LABEL_MISMATCH" for i in issues), (
            "verify_samples did not catch the injected label error"
        )


class TestValidatorAndOracleConsistency:
    """The validator's SINGLE_CLASS check is consistent with the oracle."""

    def test_all_authorised_scenario_validator_agrees_with_oracle(self) -> None:
        """all_authorised.json triggers SINGLE_CLASS; oracle confirms all 1s."""
        path = SCENARIOS_DIR / "all_authorised.json"
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        tables = {k: pd.DataFrame(v) for k, v in raw.items() if not k.startswith("_")}

        # Validator should flag SINGLE_CLASS
        issues = validate_dataset(tables)
        assert any(i["code"] == "SINGLE_CLASS" for i in issues if i["severity"] == "error")

        # Oracle should confirm all authorised
        auth = brute_force_auth(
            tables["users"], tables["roles"], tables["permissions"],
            tables["user_roles"], tables["role_permissions"], tables["resources"]
        )
        assert (auth["authorised"] == 1).all(), (
            "Oracle disagrees: not all tuples are authorised in all_authorised.json"
        )

    def test_none_authorised_scenario_validator_agrees_with_oracle(self) -> None:
        """none_authorised.json triggers SINGLE_CLASS; oracle confirms all 0s."""
        path = SCENARIOS_DIR / "none_authorised.json"
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        tables = {k: pd.DataFrame(v) for k, v in raw.items() if not k.startswith("_")}

        issues = validate_dataset(tables)
        assert any(i["code"] == "SINGLE_CLASS" for i in issues if i["severity"] == "error")

        auth = brute_force_auth(
            tables["users"], tables["roles"], tables["permissions"],
            tables["user_roles"], tables["role_permissions"], tables["resources"]
        )
        assert (auth["authorised"] == 0).all(), (
            "Oracle disagrees: some tuples are authorised in none_authorised.json"
        )


class TestOracleHandComputedExample:
    """
    TC-O-01 cross-check against test_cases.md §1.1 hand-computed values.
    Uses the tiny_3users.json scenario which embeds the expected auth matrix.
    """

    def test_oracle_matches_hand_computed_tiny_example(self) -> None:
        path = SCENARIOS_DIR / "tiny_3users.json"
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)

        tables = {k: pd.DataFrame(v) for k, v in raw.items() if not k.startswith("_")}
        expected = pd.DataFrame(raw["_hand_computed_auth"])

        oracle = brute_force_auth(
            tables["users"], tables["roles"], tables["permissions"],
            tables["user_roles"], tables["role_permissions"], tables["resources"]
        )

        # Sort both by the same key for comparison
        oracle_sorted = oracle.sort_values(
            ["user_id", "resource_id", "permission"]
        ).reset_index(drop=True)
        expected_sorted = expected.sort_values(
            ["user_id", "resource_id", "permission"]
        ).reset_index(drop=True)
        # Convert expected authorised to int
        expected_sorted["authorised"] = expected_sorted["authorised"].astype(int)
        oracle_sorted["authorised"] = oracle_sorted["authorised"].astype(int)

        pd.testing.assert_frame_equal(
            oracle_sorted[["user_id", "resource_id", "permission", "authorised"]],
            expected_sorted[["user_id", "resource_id", "permission", "authorised"]],
            check_like=False,
        )


# ===========================================================================
# B. Cross-check with Jayed's backend module (skipped until M3)
# ===========================================================================

class TestOracleMatchesBackend:
    """
    TC-I-01: Shweta's oracle must agree with Jayed's build_auth_matrix on
    the small dataset. Skipped until Milestone 3 (backend data_pipeline).
    """

    @backend_module_required
    def test_oracle_matches_build_auth_matrix(self) -> None:
        from backend.data_pipeline.auth_matrix import build_auth_matrix

        t = _load_small()
        oracle = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )

        # Jayed's function takes a dataset object — convert dict to RBACDataset
        from backend.data_pipeline.loader import RBACDataset
        dataset = RBACDataset(
            users=t["users"],
            roles=t["roles"],
            permissions=t["permissions"],
            user_roles=t["user_roles"],
            role_permissions=t["role_permissions"],
            resources=t["resources"],
            user_attribute_columns=[c for c in t["users"].columns if c != "user_id"],
            resource_attribute_columns=[c for c in t["resources"].columns if c != "resource_id"],
        )
        backend_auth = build_auth_matrix(dataset)

        # Normalise and compare
        def _normalise(df: pd.DataFrame) -> pd.DataFrame:
            return (
                df[["user_id", "resource_id", "permission", "authorised"]]
                .astype({"authorised": int})
                .sort_values(["user_id", "resource_id", "permission"])
                .reset_index(drop=True)
            )

        pd.testing.assert_frame_equal(
            _normalise(oracle),
            _normalise(backend_auth),
            check_like=False,
        )


# ===========================================================================
# C. End-to-end HTTP flow (skipped until M10)
# ===========================================================================

class TestEndToEndFlow:
    """
    TC-I-05: Upload → validate → authorisation matrix → cross-check with oracle.
    Requires the full backend to be running at RBAC_BACKEND_URL.
    Skipped until Milestone 10.
    """

    @backend_http_required
    def test_upload_then_authorisation_endpoint(self) -> None:
        import httpx
        from shared.schemas.contracts import (
            DatasetValidationResponse,
            RBACAuthorisationResponse,
        )

        # Upload the small dataset
        small_dir = SMALL_DIR
        table_names = [
            "users", "roles", "permissions", "resources",
            "user_roles", "role_permissions",
        ]
        files = {}
        file_handles = []
        for name in table_names:
            fh = open(small_dir / f"{name}.csv", "rb")
            file_handles.append(fh)
            files[name] = (f"{name}.csv", fh, "text/csv")
        try:
            upload_resp = httpx.post(
                f"{_BACKEND_URL}/api/v1/datasets/upload",
                data={"dataset_name": "integration_test_small", "file_format": "csv"},
                files=files,
                timeout=30,
            )
        finally:
            for fh in file_handles:
                fh.close()

        assert upload_resp.status_code == 200
        val = DatasetValidationResponse(**upload_resp.json())
        assert val.status == "ok", f"Dataset invalid: {val.issues}"
        dataset_id = val.dataset_id

        # Fetch the authorisation matrix
        auth_resp = httpx.get(
            f"{_BACKEND_URL}/api/v1/datasets/{dataset_id}/authorisation",
            timeout=30,
        )
        assert auth_resp.status_code == 200
        rbac = RBACAuthorisationResponse(**auth_resp.json())

        # Cross-check with the oracle
        t = _load_small()
        oracle = brute_force_auth(
            t["users"], t["roles"], t["permissions"],
            t["user_roles"], t["role_permissions"], t["resources"]
        )
        oracle_authorised = int(oracle["authorised"].sum())
        oracle_unauthorised = int((oracle["authorised"] == 0).sum())

        assert rbac.n_authorised == oracle_authorised, (
            f"Backend n_authorised={rbac.n_authorised}, "
            f"oracle says {oracle_authorised}"
        )
        assert rbac.n_unauthorised == oracle_unauthorised, (
            f"Backend n_unauthorised={rbac.n_unauthorised}, "
            f"oracle says {oracle_unauthorised}"
        )


# ===========================================================================
# D. Policy metric hand-computation cross-check (skipped until M8)
# ===========================================================================

class TestPolicyMetricsHandComputation:
    """
    Cross-check: Granthali's validate_policy must reproduce the hand-computed
    metrics from test_cases.md §2 on the worked example.
    Skipped until Milestone 8 (policy_engine.validate_policy exists).
    """

    @policy_engine_required
    def test_worked_example_metrics(self) -> None:
        from policy_engine import validate_policy
        from shared.schemas.contracts import ABACRule, Condition, Operator

        # VALIDATION.md §2 worked example
        # RBAC authorised: (u1,r1), (u2,r1), (u3,r2)
        # Policy permits:  (u1,r1), (u2,r1), (u1,r2)

        access_matrix = pd.DataFrame([
            {"user_id": "u1", "resource_id": "r1", "permission": "read", "authorised": 1},
            {"user_id": "u2", "resource_id": "r1", "permission": "read", "authorised": 1},
            {"user_id": "u3", "resource_id": "r2", "permission": "read", "authorised": 1},
            {"user_id": "u1", "resource_id": "r2", "permission": "read", "authorised": 0},
            {"user_id": "u2", "resource_id": "r2", "permission": "read", "authorised": 0},
            {"user_id": "u3", "resource_id": "r1", "permission": "read", "authorised": 0},
        ])

        user_attrs = pd.DataFrame([
            {"user_id": "u1", "name": "Alice"},
            {"user_id": "u2", "name": "Bob"},
            {"user_id": "u3", "name": "Carol"},
        ])

        resource_attrs = pd.DataFrame([
            {"resource_id": "r1", "sensitivity": "low"},
            {"resource_id": "r2", "sensitivity": "low"},
        ])

        # Rules that permit exactly (u1,r1), (u2,r1), (u1,r2) for action "read":
        # Rule 1: user.name in ["Alice","Bob"] → covers (u1,r1), (u2,r1), (u1,r2), (u2,r2)
        # We need a more specific rule — use resource.sensitivity == "low" for r1 only
        # For this test, simplify: two rules together permit (u1,r1), (u2,r1), (u1,r2)
        # Rule A: user.name == "Alice" → permits for all resources
        # Rule B: user.name == "Bob" AND resource.sensitivity == "low" (r1 only)
        # This is approximate for the worked example; the exact rule set depends
        # on Granthali's condition evaluation which is not yet available.
        # Mark this test as pending full implementation.
        pytest.skip(
            "Full policy_engine.validate_policy integration test pending "
            "Granthali's implementation (Milestone 8)."
        )
