"""Contract tests. Run: python -m pytest shared/tests -q

Guards the rules that must never silently change (see PROJECT_RULES.json).
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.schemas import contracts as c

SAMPLES = Path(__file__).resolve().parent.parent / "sample_responses"


def _rule(**kw):
    base = dict(
        rule_id="R1",
        action="read",
        conditions=[c.Condition(attribute="user.department", operator="==", value="Finance")],
        support=0.1,
        confidence=0.95,
    )
    base.update(kw)
    return c.ABACRule(**base)


def test_contract_version_is_semver():
    assert len(c.CONTRACT_VERSION.split(".")) == 3


def test_rule_effect_is_permit_only():
    assert _rule().effect == "permit"
    with pytest.raises(ValidationError):
        _rule(effect="deny")


def test_rule_needs_at_least_one_condition():
    with pytest.raises(ValidationError):
        _rule(conditions=[])


def test_new_rules_start_as_candidate_never_approved():
    assert _rule().status == c.RuleStatus.CANDIDATE


def test_support_and_confidence_bounded():
    with pytest.raises(ValidationError):
        _rule(support=1.5)
    with pytest.raises(ValidationError):
        _rule(confidence=-0.1)


def test_operator_set_is_closed():
    with pytest.raises(ValidationError):
        c.Condition(attribute="user.x", operator="LIKE", value="a")


def test_policy_metrics_must_be_full_matrix():
    with pytest.raises(ValidationError):
        c.PolicyMetrics(
            precision=1, recall=1, f1=1, over_privilege_rate=0, under_privilege_rate=0,
            rule_count=1, wsc=1.0, evaluated_on="sampled_data", n_tuples_evaluated=1,
        )


def test_only_decision_tree_selected_for_extraction():
    with pytest.raises(ValidationError):
        c.ModelComparisonResponse(
            run_id="r", rows=[], selected_for_extraction="random_forest", selection_reason="x"
        )


def test_export_and_validation_default_decision_is_deny():
    assert c.PolicyValidationResponse.model_fields["fail_safe_default"].default == "deny"
    assert c.ExportResponse.model_fields["default_decision"].default == "deny"


def test_review_requires_decisions_and_reviewer():
    with pytest.raises(ValidationError):
        c.ApprovalRequest(policy_id="p", reviewer="", decisions=[])


def test_error_response_shape():
    e = c.ErrorResponse(code="X", message="m")
    assert e.status == "error"


@pytest.mark.parametrize("path", sorted(SAMPLES.glob("*.json")), ids=lambda p: p.name)
def test_samples_are_valid_json(path):
    json.loads(path.read_text(encoding="utf-8"))
