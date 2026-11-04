"""
tests/test_api.py
------------------
Contract tests for the FastAPI backend.

Two categories:
  1. Mock-validation tests (NO backend required) — validate all
     shared/sample_responses/*.json against their Pydantic models.
     These always run.

  2. Live endpoint tests (backend required) — marked with
     @pytest.mark.skipif so they are skipped until the backend exists.
     Set env var RBAC_BACKEND_URL (e.g. http://localhost:8000) to enable.

Owner : Shweta Suresh Kidile
Ref   : docs/modules/DATA_CONTRACTS.md, shared/schemas/contracts.py
        data_engineering/documentation/test_cases.md §7
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Pydantic models from contracts.py (read-only import)
# ---------------------------------------------------------------------------
from shared.schemas.contracts import (
    DatasetValidationResponse,
    RBACAuthorisationResponse,
    TrainingResponse,
    ModelComparisonResponse,
    ExtractedRulesResponse,
    OptimisedPolicyResponse,
    PolicyValidationResponse,
    ApprovalRequest,
    ApprovalResponse,
    ExportRequest,
    ExportResponse,
    ErrorResponse,
)

SAMPLE_RESPONSES_DIR = Path("shared/sample_responses")

# ---------------------------------------------------------------------------
# Backend availability
# ---------------------------------------------------------------------------
_BACKEND_URL = os.environ.get("RBAC_BACKEND_URL", "").strip()
_BACKEND_AVAILABLE = bool(_BACKEND_URL)

backend_required = pytest.mark.skipif(
    not _BACKEND_AVAILABLE,
    reason=(
        "Backend not available. Set RBAC_BACKEND_URL env var to enable "
        "live endpoint tests (e.g. http://localhost:8000)."
    ),
)


# ===========================================================================
# 1. Mock-validation tests (always run — no backend needed)
# ===========================================================================

class TestSampleResponsesValidateAgainstContracts:
    """TC-A-01: All shared/sample_responses/*.json validate against Pydantic models."""

    def _load(self, filename: str) -> dict:
        path = SAMPLE_RESPONSES_DIR / filename
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_dataset_validation_ok(self) -> None:
        data = self._load("dataset_validation_ok.json")
        model = DatasetValidationResponse(**data)
        assert model.status == "ok"

    def test_dataset_validation_invalid(self) -> None:
        data = self._load("dataset_validation_invalid.json")
        model = DatasetValidationResponse(**data)
        assert model.status == "invalid"
        assert model.dataset_id is None

    def test_rbac_authorisation(self) -> None:
        data = self._load("rbac_authorisation.json")
        model = RBACAuthorisationResponse(**data)
        assert model.status == "ok"
        assert model.n_authorised + model.n_unauthorised == model.total_possible_tuples

    def test_training_response(self) -> None:
        data = self._load("training_response.json")
        model = TrainingResponse(**data)
        assert model.status == "ok"
        assert len(model.models) == 3

    def test_model_comparison(self) -> None:
        data = self._load("model_comparison.json")
        model = ModelComparisonResponse(**data)
        assert model.selected_for_extraction == "decision_tree"

    def test_extracted_rules(self) -> None:
        data = self._load("extracted_rules.json")
        model = ExtractedRulesResponse(**data)
        assert model.n_rules == len(model.rules)

    def test_optimised_policy(self) -> None:
        data = self._load("optimised_policy.json")
        model = OptimisedPolicyResponse(**data)
        assert model.metrics.evaluated_on == "full_access_matrix"

    def test_policy_validation(self) -> None:
        data = self._load("policy_validation.json")
        model = PolicyValidationResponse(**data)
        assert model.fail_safe_default == "deny"
        assert 0.0 <= model.metrics.precision <= 1.0
        assert 0.0 <= model.metrics.recall <= 1.0

    def test_approval_request(self) -> None:
        data = self._load("approval_request.json")
        model = ApprovalRequest(**data)
        assert len(model.decisions) >= 1

    def test_approval_response(self) -> None:
        data = self._load("approval_response.json")
        model = ApprovalResponse(**data)
        assert model.status == "ok"

    def test_export_request(self) -> None:
        data = self._load("export_request.json")
        model = ExportRequest(**data)
        assert model.format in ("json", "xacml")

    def test_export_response(self) -> None:
        data = self._load("export_response.json")
        model = ExportResponse(**data)
        assert model.default_decision == "deny"
        assert model.n_rules_exported >= 0

    def test_error_response(self) -> None:
        data = self._load("error_response.json")
        model = ErrorResponse(**data)
        assert model.status == "error"
        assert model.code  # must be non-empty


class TestContractInvariants:
    """Verify critical invariants from contracts.py."""

    def test_training_response_exactly_one_rule_extraction_model(self) -> None:
        """is_rule_extraction_model must be True for exactly one model."""
        path = SAMPLE_RESPONSES_DIR / "training_response.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        model = TrainingResponse(**data)
        extraction_models = [m for m in model.models if m.is_rule_extraction_model]
        assert len(extraction_models) == 1, (
            f"Expected exactly 1 rule extraction model, got {len(extraction_models)}"
        )
        assert extraction_models[0].model_name == "decision_tree"

    def test_all_rules_have_permit_effect(self) -> None:
        """All extracted ABAC rules must have effect == 'permit'."""
        path = SAMPLE_RESPONSES_DIR / "extracted_rules.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        model = ExtractedRulesResponse(**data)
        for rule in model.rules:
            assert rule.effect == "permit", (
                f"Rule {rule.rule_id} has effect '{rule.effect}', expected 'permit'"
            )

    def test_policy_validation_on_full_matrix(self) -> None:
        """PolicyMetrics.evaluated_on must always be 'full_access_matrix'."""
        for fname in ("policy_validation.json", "optimised_policy.json"):
            path = SAMPLE_RESPONSES_DIR / fname
            data = json.loads(path.read_text(encoding="utf-8"))
            # extract metrics
            metrics_data = data.get("metrics", {})
            assert metrics_data.get("evaluated_on") == "full_access_matrix", (
                f"{fname}: evaluated_on is not 'full_access_matrix'"
            )

    def test_export_default_decision_is_deny(self) -> None:
        path = SAMPLE_RESPONSES_DIR / "export_response.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        model = ExportResponse(**data)
        assert model.default_decision == "deny"

    def test_authorisation_density_between_0_and_1(self) -> None:
        path = SAMPLE_RESPONSES_DIR / "rbac_authorisation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        model = RBACAuthorisationResponse(**data)
        assert 0.0 <= model.authorisation_density <= 1.0

    def test_rule_conditions_non_empty(self) -> None:
        path = SAMPLE_RESPONSES_DIR / "extracted_rules.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        model = ExtractedRulesResponse(**data)
        for rule in model.rules:
            assert len(rule.conditions) >= 1, (
                f"Rule {rule.rule_id} has no conditions"
            )

    def test_condition_attributes_are_prefixed(self) -> None:
        """All condition attributes must start with 'user.' or 'resource.'."""
        path = SAMPLE_RESPONSES_DIR / "extracted_rules.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        model = ExtractedRulesResponse(**data)
        for rule in model.rules:
            for cond in rule.conditions:
                assert cond.attribute.startswith("user.") or \
                       cond.attribute.startswith("resource."), (
                    f"Condition attribute '{cond.attribute}' is not prefixed"
                )


# ===========================================================================
# 2. Live endpoint tests (skipped unless RBAC_BACKEND_URL is set)
# ===========================================================================

class TestLiveEndpoints:
    """
    TC-A-02 through TC-A-06: Live API contract tests.

    These tests require the backend to be running. They are skipped
    automatically when RBAC_BACKEND_URL is not set.

    To run: set RBAC_BACKEND_URL=http://localhost:8000
            python -m pytest tests/test_api.py -k live -v
    """

    @backend_required
    def test_health_endpoint(self) -> None:
        """GET /health should return {"status": "ok"}."""
        import httpx
        resp = httpx.get(f"{_BACKEND_URL}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    @backend_required
    def test_upload_endpoint_validates_small_dataset(self) -> None:
        """TC-A-02: POST /api/v1/datasets/upload returns DatasetValidationResponse."""
        import httpx
        from pathlib import Path

        small_dir = Path("data_engineering/sample_datasets/small")
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
            resp = httpx.post(
                f"{_BACKEND_URL}/api/v1/datasets/upload",
                data={"dataset_name": "test_small", "file_format": "csv"},
                files=files,
                timeout=30,
            )
        finally:
            for fh in file_handles:
                fh.close()

        assert resp.status_code == 200, (
            f"Upload failed with status {resp.status_code}: {resp.text}"
        )
        model = DatasetValidationResponse(**resp.json())
        assert model.status in ("ok", "invalid")

    @backend_required
    def test_unknown_dataset_returns_404(self) -> None:
        """GET /api/v1/datasets/ds_NONEXISTENT/authorisation → 404."""
        import httpx
        resp = httpx.get(
            f"{_BACKEND_URL}/api/v1/datasets/ds_NONEXISTENT/authorisation",
            timeout=10,
        )
        assert resp.status_code == 404
        model = ErrorResponse(**resp.json())
        assert model.status == "error"
