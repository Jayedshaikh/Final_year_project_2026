"""Contract tests for all nine API endpoints.

Each test:
  1. Calls the endpoint via TestClient.
  2. Asserts the HTTP status code.
  3. Validates the response body against the matching Pydantic contract model.

Also tests negative cases: 404 for unknown ids, 400 for bad input, 409 for export
before approval, 422 for malformed bodies.
"""
from __future__ import annotations

import io
import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from shared.schemas.contracts import (
    ApprovalResponse,
    DatasetValidationResponse,
    ErrorResponse,
    ExportResponse,
    ExtractedRulesResponse,
    ModelComparisonResponse,
    OptimisedPolicyResponse,
    PolicyValidationResponse,
    RBACAuthorisationResponse,
    TrainingResponse,
)

client = TestClient(app, raise_server_exceptions=False)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _csv_file(content: str) -> bytes:
    return content.encode("utf-8")


def _upload_small_dataset() -> str:
    """Upload the small test dataset and return the dataset_id."""
    files = {
        "users": ("users.csv", _csv_file("user_id,department,position\nu1,finance,manager\nu2,hr,staff\n"), "text/csv"),
        "roles": ("roles.csv", _csv_file("role_id\nr_fin\nr_hr\n"), "text/csv"),
        "permissions": ("permissions.csv", _csv_file("permission_id\nread\nwrite\n"), "text/csv"),
        "user_roles": ("user_roles.csv", _csv_file("user_id,role_id\nu1,r_fin\nu2,r_hr\n"), "text/csv"),
        "role_permissions": ("role_permissions.csv", _csv_file("role_id,permission_id,resource_id\nr_fin,read,\nr_fin,write,\nr_hr,read,\n"), "text/csv"),
        "resources": ("resources.csv", _csv_file("resource_id,type,sensitivity\nres1,report,low\nres2,record,high\n"), "text/csv"),
    }
    data = {"dataset_name": "test_dataset", "file_format": "csv"}
    response = client.post("/api/v1/datasets/upload", files=files, data=data)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    return body["dataset_id"]


def _run_training(dataset_id: str, seed: int = 42) -> str:
    """Trigger training and return the run_id."""
    payload = {
        "dataset_id": dataset_id,
        "models": ["decision_tree", "random_forest", "gradient_boosting"],
        "random_seed": seed,
        "cv_folds": 2,
        "f1_target": 0.5,
        "min_support": 0.0,
        "min_confidence": 0.0,
    }
    response = client.post("/api/v1/training/run", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["run_id"]


def _optimise(run_id: str) -> str:
    """Optimise and return policy_id."""
    response = client.post(f"/api/v1/policies/optimise/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()["policy_id"]


def _approve_first_rule(policy_id: str, rules: list) -> None:
    """Approve the first rule in the policy."""
    if not rules:
        return
    payload = {
        "policy_id": policy_id,
        "reviewer": "test_admin",
        "decisions": [{"rule_id": rules[0]["rule_id"], "decision": "approve"}],
    }
    response = client.post(f"/api/v1/policies/{policy_id}/review", json=payload)
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #

class TestHealth:
    def test_health_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# Dataset upload
# --------------------------------------------------------------------------- #

class TestDatasetUpload:
    def test_upload_ok_matches_contract(self):
        files = {
            "users": ("users.csv", _csv_file("user_id,dept\nu1,eng\n"), "text/csv"),
            "roles": ("roles.csv", _csv_file("role_id\nr1\n"), "text/csv"),
            "permissions": ("permissions.csv", _csv_file("permission_id\nread\n"), "text/csv"),
            "user_roles": ("user_roles.csv", _csv_file("user_id,role_id\nu1,r1\n"), "text/csv"),
            "role_permissions": ("role_permissions.csv", _csv_file("role_id,permission_id,resource_id\nr1,read,\n"), "text/csv"),
            "resources": ("resources.csv", _csv_file("resource_id,type\nres1,doc\n"), "text/csv"),
        }
        data = {"dataset_name": "my_dataset", "file_format": "csv"}
        response = client.post("/api/v1/datasets/upload", files=files, data=data)
        assert response.status_code == 200
        validated = DatasetValidationResponse(**response.json())
        assert validated.status == "ok"
        assert validated.dataset_id is not None

    def test_upload_invalid_format_returns_400(self):
        response = client.post(
            "/api/v1/datasets/upload",
            data={"dataset_name": "bad", "file_format": "xml"},
            files={"users": ("u.csv", b"user_id\nu1\n", "text/csv"),
                   "roles": ("r.csv", b"role_id\nr1\n", "text/csv"),
                   "permissions": ("p.csv", b"permission_id\nread\n", "text/csv"),
                   "user_roles": ("ur.csv", b"user_id,role_id\nu1,r1\n", "text/csv"),
                   "role_permissions": ("rp.csv", b"role_id,permission_id\nr1,read\n", "text/csv"),
                   "resources": ("res.csv", b"resource_id\nres1\n", "text/csv")},
        )
        assert response.status_code == 400
        ErrorResponse(**response.json())

    def test_upload_missing_required_column_returns_400(self):
        files = {
            "users": ("users.csv", _csv_file("uid,dept\nu1,eng\n"), "text/csv"),  # wrong column
            "roles": ("roles.csv", _csv_file("role_id\nr1\n"), "text/csv"),
            "permissions": ("permissions.csv", _csv_file("permission_id\nread\n"), "text/csv"),
            "user_roles": ("user_roles.csv", _csv_file("user_id,role_id\nu1,r1\n"), "text/csv"),
            "role_permissions": ("role_permissions.csv", _csv_file("role_id,permission_id\nr1,read\n"), "text/csv"),
            "resources": ("resources.csv", _csv_file("resource_id\nres1\n"), "text/csv"),
        }
        data = {"dataset_name": "bad", "file_format": "csv"}
        response = client.post("/api/v1/datasets/upload", files=files, data=data)
        assert response.status_code == 400


# --------------------------------------------------------------------------- #
# RBAC authorisation
# --------------------------------------------------------------------------- #

class TestAuthorisation:
    def test_authorisation_ok_matches_contract(self):
        ds_id = _upload_small_dataset()
        response = client.get(f"/api/v1/datasets/{ds_id}/authorisation")
        assert response.status_code == 200
        validated = RBACAuthorisationResponse(**response.json())
        assert validated.dataset_id == ds_id

    def test_unknown_dataset_returns_404(self):
        response = client.get("/api/v1/datasets/ds_999/authorisation")
        assert response.status_code == 404
        ErrorResponse(**response.json())


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #

class TestTraining:
    def test_training_ok_matches_contract(self):
        ds_id = _upload_small_dataset()
        payload = {
            "dataset_id": ds_id,
            "models": ["decision_tree"],
            "random_seed": 42,
            "cv_folds": 2,
            "f1_target": 0.5,
            "min_support": 0.0,
            "min_confidence": 0.0,
        }
        response = client.post("/api/v1/training/run", json=payload)
        assert response.status_code == 200
        validated = TrainingResponse(**response.json())
        assert validated.dataset_id == ds_id
        assert len(validated.models) == 1

    def test_unknown_dataset_returns_404(self):
        response = client.post(
            "/api/v1/training/run",
            json={"dataset_id": "ds_999", "random_seed": 42},
        )
        assert response.status_code == 404
        ErrorResponse(**response.json())

    def test_malformed_body_returns_422(self):
        response = client.post("/api/v1/training/run", json={"not_a_field": True})
        assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Model comparison
# --------------------------------------------------------------------------- #

class TestComparison:
    def test_comparison_ok_matches_contract(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        response = client.get(f"/api/v1/training/{run_id}/comparison")
        assert response.status_code == 200
        validated = ModelComparisonResponse(**response.json())
        assert validated.run_id == run_id
        assert validated.selected_for_extraction == "decision_tree"

    def test_unknown_run_returns_404(self):
        response = client.get("/api/v1/training/run_999/comparison")
        assert response.status_code == 404
        ErrorResponse(**response.json())


# --------------------------------------------------------------------------- #
# Extracted rules
# --------------------------------------------------------------------------- #

class TestExtractedRules:
    def test_rules_ok_matches_contract(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        response = client.get(f"/api/v1/training/{run_id}/rules")
        assert response.status_code == 200
        validated = ExtractedRulesResponse(**response.json())
        assert validated.run_id == run_id
        assert validated.n_rules == len(validated.rules)

    def test_unknown_run_returns_404(self):
        response = client.get("/api/v1/training/run_999/rules")
        assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Optimise policy
# --------------------------------------------------------------------------- #

class TestOptimise:
    def test_optimise_ok_matches_contract(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        response = client.post(f"/api/v1/policies/optimise/{run_id}")
        assert response.status_code == 200
        validated = OptimisedPolicyResponse(**response.json())
        assert validated.run_id == run_id
        assert validated.policy_id.startswith("pol_")

    def test_unknown_run_returns_404(self):
        response = client.post("/api/v1/policies/optimise/run_999")
        assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Policy validation
# --------------------------------------------------------------------------- #

class TestPolicyValidation:
    def test_validation_ok_matches_contract(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)
        response = client.get(f"/api/v1/policies/{policy_id}/validation")
        assert response.status_code == 200
        validated = PolicyValidationResponse(**response.json())
        assert validated.policy_id == policy_id
        assert validated.fail_safe_default == "deny"

    def test_unknown_policy_returns_404(self):
        response = client.get("/api/v1/policies/pol_999/validation")
        assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Administrator review
# --------------------------------------------------------------------------- #

class TestReview:
    def test_review_approve_matches_contract(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        # Get the rules
        rules_resp = client.get(f"/api/v1/training/{run_id}/rules").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules extracted; skipping review test.")

        payload = {
            "policy_id": policy_id,
            "reviewer": "admin",
            "decisions": [{"rule_id": rules[0]["rule_id"], "decision": "approve"}],
        }
        response = client.post(f"/api/v1/policies/{policy_id}/review", json=payload)
        assert response.status_code == 200
        validated = ApprovalResponse(**response.json())
        assert validated.n_approved >= 1

    def test_policy_id_mismatch_returns_400(self):
        response = client.post(
            "/api/v1/policies/pol_001/review",
            json={
                "policy_id": "pol_999",
                "reviewer": "admin",
                "decisions": [{"rule_id": "R001", "decision": "approve"}],
            },
        )
        assert response.status_code == 400

    def test_unknown_policy_returns_404(self):
        response = client.post(
            "/api/v1/policies/pol_999/review",
            json={
                "policy_id": "pol_999",
                "reviewer": "admin",
                "decisions": [{"rule_id": "R001", "decision": "approve"}],
            },
        )
        assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #

class TestExport:
    def test_export_before_approval_returns_409(self):
        """Export must return 409 when no rules have been approved yet."""
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)
        # At this point no rules have been approved — export must fail with 409
        response = client.post(
            f"/api/v1/policies/{policy_id}/export",
            json={"policy_id": policy_id, "format": "json"},
        )
        assert response.status_code == 409, (
            f"Expected 409 (no approved rules), got {response.status_code}: {response.text}"
        )
        ErrorResponse(**response.json())

    def test_export_after_approval_matches_contract(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        # Get optimised rules
        optimised = client.get(f"/api/v1/policies/{policy_id}/validation").json()
        rules_resp = client.post(f"/api/v1/policies/optimise/{run_id}").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules to approve; skipping export test.")

        _approve_first_rule(policy_id, rules)

        response = client.post(
            f"/api/v1/policies/{policy_id}/export",
            json={"policy_id": policy_id, "format": "json"},
        )
        assert response.status_code == 200
        validated = ExportResponse(**response.json())
        assert validated.policy_id == policy_id
        assert validated.default_decision == "deny"
        assert validated.n_rules_exported >= 1
        # Content must be valid JSON
        parsed = json.loads(validated.content)
        assert "default_decision" in parsed

    def test_unknown_policy_returns_404(self):
        response = client.post(
            "/api/v1/policies/pol_999/export",
            json={"policy_id": "pol_999", "format": "json"},
        )
        assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Additional contract and state-machine tests (Guide section 10 completeness)
# --------------------------------------------------------------------------- #

class TestXACMLExport:
    """XACML export format must parse as XML and contain deny default."""

    def test_xacml_export_parses_as_xml(self):
        import xml.etree.ElementTree as ET
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        # Get rules and approve one
        rules_resp = client.get(f"/api/v1/training/{run_id}/rules").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules extracted.")

        _approve_first_rule(policy_id, rules)

        response = client.post(
            f"/api/v1/policies/{policy_id}/export",
            json={"policy_id": policy_id, "format": "xacml"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["format"] == "xacml"
        assert body["default_decision"] == "deny"
        # Content must parse as XML
        ET.fromstring(body["content"])  # raises if not valid XML


class TestRuleEditWorkflow:
    """Admin can edit a rule and the state must reflect 'edited' (pending re-validation)."""

    def test_edit_rule_returns_edited_pending(self):
        from shared.schemas.contracts import Condition
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        rules_resp = client.get(f"/api/v1/training/{run_id}/rules").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules extracted.")

        # Edit the first rule
        edited_conditions = [
            {"attribute": "user.department", "operator": "==", "value": "finance"}
        ]
        payload = {
            "policy_id": policy_id,
            "reviewer": "admin",
            "decisions": [{
                "rule_id": rules[0]["rule_id"],
                "decision": "edit",
                "edited_conditions": edited_conditions,
                "comment": "Narrowed to finance only",
            }],
        }
        response = client.post(f"/api/v1/policies/{policy_id}/review", json=payload)
        assert response.status_code == 200
        body = ApprovalResponse(**response.json())
        assert body.n_edited_pending_revalidation >= 1

    def test_edited_rule_cannot_be_exported_until_approved(self):
        """An edited rule must be re-approved before it can be exported."""
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        rules_resp = client.get(f"/api/v1/training/{run_id}/rules").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules extracted.")

        # Edit the first rule (status -> 'edited', not exportable)
        edit_payload = {
            "policy_id": policy_id,
            "reviewer": "admin",
            "decisions": [{
                "rule_id": rules[0]["rule_id"],
                "decision": "edit",
                "edited_conditions": [
                    {"attribute": "user.department", "operator": "==", "value": "finance"}
                ],
            }],
        }
        client.post(f"/api/v1/policies/{policy_id}/review", json=edit_payload)

        # Try to export — must fail with 409 (no approved rules)
        response = client.post(
            f"/api/v1/policies/{policy_id}/export",
            json={"policy_id": policy_id, "format": "json"},
        )
        assert response.status_code == 409


class TestRejectWorkflow:
    """Rejected rules are excluded from export and counted correctly."""

    def test_reject_rule_counts_correctly(self):
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        rules_resp = client.get(f"/api/v1/training/{run_id}/rules").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules extracted.")

        reject_payload = {
            "policy_id": policy_id,
            "reviewer": "admin",
            "decisions": [{
                "rule_id": rules[0]["rule_id"],
                "decision": "reject",
                "comment": "Not useful",
            }],
        }
        response = client.post(f"/api/v1/policies/{policy_id}/review", json=reject_payload)
        assert response.status_code == 200
        body = ApprovalResponse(**response.json())
        assert body.n_rejected >= 1

    def test_all_rejected_rules_cannot_export(self):
        """If all rules are rejected, export must return 409."""
        ds_id = _upload_small_dataset()
        run_id = _run_training(ds_id)
        policy_id = _optimise(run_id)

        rules_resp = client.get(f"/api/v1/training/{run_id}/rules").json()
        rules = rules_resp.get("rules", [])
        if not rules:
            pytest.skip("No rules extracted.")

        # Reject ALL rules
        decisions = [
            {"rule_id": r["rule_id"], "decision": "reject"} for r in rules
        ]
        reject_payload = {
            "policy_id": policy_id,
            "reviewer": "admin",
            "decisions": decisions,
        }
        client.post(f"/api/v1/policies/{policy_id}/review", json=reject_payload)

        response = client.post(
            f"/api/v1/policies/{policy_id}/export",
            json={"policy_id": policy_id, "format": "json"},
        )
        assert response.status_code == 409


class TestContractIntegrity:
    """Every API response must parse against its Pydantic contract model (Rule R6)."""

    def test_training_response_is_contract_valid(self):
        ds_id = _upload_small_dataset()
        response = client.post(
            "/api/v1/training/run",
            json={"dataset_id": ds_id, "random_seed": 42, "cv_folds": 2,
                  "models": ["decision_tree"], "f1_target": 0.5,
                  "min_support": 0.0, "min_confidence": 0.0},
        )
        assert response.status_code == 200
        validated = TrainingResponse(**response.json())
        assert validated.status == "ok"
        assert validated.n_train + validated.n_test == validated.n_positive + validated.n_negative

    def test_error_response_has_code_and_message(self):
        """Every non-2xx response must have status=error, code, and message."""
        response = client.get("/api/v1/datasets/ds_NONEXISTENT/authorisation")
        assert response.status_code == 404
        body = response.json()
        assert body["status"] == "error"
        assert "code" in body
        assert "message" in body
        ErrorResponse(**body)

    def test_health_endpoint_not_under_api_v1(self):
        """/health is outside the /api/v1 contract (Decision D-009)."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        # Must NOT exist under /api/v1
        response2 = client.get("/api/v1/health")
        assert response2.status_code == 404
