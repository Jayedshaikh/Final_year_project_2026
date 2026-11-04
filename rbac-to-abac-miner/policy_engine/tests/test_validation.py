"""Tests for policy validation against full access matrix."""

import pandas as pd
import pytest
from shared.schemas.contracts import ABACRule, Condition, PolicyMetrics
from policy_engine.policy_validator.validator import validate_policy


def test_validate_empty_policy_denies_all():
    """Empty policy should deny all tuples (default deny)."""
    # Full access matrix: 2 users x 2 resources x 1 permission = 4 tuples
    # All authorized by RBAC
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u2"],
        "resource_id": ["r1", "r2", "r1", "r2"],
        "permission": ["read", "read", "read", "read"],
        "authorised": [1, 1, 1, 1],
    })
    
    user_attrs_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "dept": ["IT", "HR"],
    })
    
    resource_attrs_df = pd.DataFrame({
        "resource_id": ["r1", "r2"],
        "type": ["server", "db"],
    })
    
    rules = []  # Empty policy
    
    metrics, over_priv, under_priv = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # Empty policy denies everything
    # All 4 tuples are FN (authorized by RBAC, denied by policy)
    assert metrics.precision == 0.0  # TP=0, FP=0 -> 0.0
    assert metrics.recall == 0.0     # TP=0, FN=4 -> 0/4 = 0.0
    assert metrics.f1 == 0.0
    assert metrics.over_privilege_rate == 0.0  # FP=0
    assert metrics.under_privilege_rate == 1.0  # FN=4, n_auth=4 -> 4/4 = 1.0
    assert metrics.rule_count == 0
    assert metrics.wsc == 0.0
    assert len(over_priv) == 0
    assert len(under_priv) == 4


def test_validate_perfect_policy():
    """Policy that exactly matches RBAC should have perfect metrics."""
    # 2 tuples: both authorized by RBAC
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "resource_id": ["r1", "r1"],
        "permission": ["read", "read"],
        "authorised": [1, 1],
    })
    
    user_attrs_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "dept": ["IT", "IT"],
    })
    
    resource_attrs_df = pd.DataFrame({
        "resource_id": ["r1"],
        "type": ["server"],
    })
    
    # Rule: permit read if user.dept == IT and resource.type == server
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="==", value="IT"),
                Condition(attribute="resource.type", operator="==", value="server"),
            ],
            status="approved",
            source="tree_path",
            support=1.0,
            confidence=1.0,
        )
    ]
    
    metrics, over_priv, under_priv = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # Perfect match: TP=2, FP=0, FN=0, TN=0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.over_privilege_rate == 0.0
    assert metrics.under_privilege_rate == 0.0
    assert metrics.rule_count == 1
    assert metrics.wsc > 0.0
    assert len(over_priv) == 0
    assert len(under_priv) == 0


def test_validate_over_privileged_example():
    """Policy permits more than RBAC (over-privileged)."""
    # 2 tuples: u1 authorized, u2 NOT authorized
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "resource_id": ["r1", "r1"],
        "permission": ["read", "read"],
        "authorised": [1, 0],
    })
    
    user_attrs_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "dept": ["IT", "HR"],
    })
    
    resource_attrs_df = pd.DataFrame({
        "resource_id": ["r1"],
        "type": ["server"],
    })
    
    # Rule: permit read for ALL (too permissive)
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="resource.type", operator="==", value="server"),
            ],
            status="approved",
            source="tree_path",
        )
    ]
    
    metrics, over_priv, under_priv = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # TP=1 (u1), FP=1 (u2), FN=0, TN=0
    assert metrics.precision == 0.5  # TP/(TP+FP) = 1/2
    assert metrics.recall == 1.0     # TP/(TP+FN) = 1/1
    assert 0.6 < metrics.f1 < 0.7    # Harmonic mean
    assert metrics.over_privilege_rate == 1.0  # FP/(FP+TN) = 1/1
    assert metrics.under_privilege_rate == 0.0
    assert len(over_priv) == 1
    assert len(under_priv) == 0
    assert over_priv[0].user_id == "u2"
    assert over_priv[0].abac_decision is True
    assert over_priv[0].rbac_decision is False


def test_validate_under_privileged_example():
    """Policy permits less than RBAC (under-privileged)."""
    # 2 tuples: both authorized by RBAC
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "resource_id": ["r1", "r1"],
        "permission": ["read", "read"],
        "authorised": [1, 1],
    })
    
    user_attrs_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "dept": ["IT", "HR"],
    })
    
    resource_attrs_df = pd.DataFrame({
        "resource_id": ["r1"],
        "type": ["server"],
    })
    
    # Rule: permit read ONLY for IT dept (too restrictive)
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="==", value="IT"),
            ],
            status="approved",
            source="tree_path",
        )
    ]
    
    metrics, over_priv, under_priv = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # TP=1 (u1), FP=0, FN=1 (u2), TN=0
    assert metrics.precision == 1.0  # TP/(TP+FP) = 1/1
    assert metrics.recall == 0.5     # TP/(TP+FN) = 1/2
    assert 0.6 < metrics.f1 < 0.7
    assert metrics.over_privilege_rate == 0.0
    assert metrics.under_privilege_rate == 0.5  # FN/(TP+FN) = 1/2
    assert len(over_priv) == 0
    assert len(under_priv) == 1
    assert under_priv[0].user_id == "u2"
    assert under_priv[0].abac_decision is False
    assert under_priv[0].rbac_decision is True


def test_validate_rejects_rejected_rules():
    """Rejected rules should not be counted in validation."""
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1"],
        "resource_id": ["r1"],
        "permission": ["read"],
        "authorised": [1],
    })
    
    user_attrs_df = pd.DataFrame({"user_id": ["u1"], "dept": ["IT"]})
    resource_attrs_df = pd.DataFrame({"resource_id": ["r1"], "type": ["server"]})
    
    # One approved rule (matches), one rejected rule (should be ignored)
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            status="approved",
            source="tree_path",
        ),
        ABACRule(
            rule_id="R002",
            action="read",
            conditions=[],  # Would match everything
            status="rejected",  # Should be ignored
            source="tree_path",
        ),
    ]
    
    metrics, _, _ = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # Only R001 counted (status=approved)
    assert metrics.rule_count == 1
    assert metrics.recall == 1.0  # R001 matches


def test_validate_handles_missing_user():
    """Missing user attributes should result in deny."""
    access_matrix_df = pd.DataFrame({
        "user_id": ["u_missing"],
        "resource_id": ["r1"],
        "permission": ["read"],
        "authorised": [1],
    })
    
    user_attrs_df = pd.DataFrame({"user_id": ["u1"], "dept": ["IT"]})  # u_missing not here
    resource_attrs_df = pd.DataFrame({"resource_id": ["r1"], "type": ["server"]})
    
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            status="approved",
            source="tree_path",
        )
    ]
    
    metrics, _, under_priv = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # Missing user -> deny -> FN (under-privileged)
    assert metrics.recall == 0.0
    assert len(under_priv) == 1


def test_validate_zero_denominators():
    """Handle zero denominators gracefully."""
    # All tuples unauthorized by RBAC
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "resource_id": ["r1", "r1"],
        "permission": ["read", "read"],
        "authorised": [0, 0],  # All unauthorized
    })
    
    user_attrs_df = pd.DataFrame({"user_id": ["u1", "u2"], "dept": ["IT", "HR"]})
    resource_attrs_df = pd.DataFrame({"resource_id": ["r1"], "type": ["server"]})
    
    rules = []  # Empty policy
    
    metrics, _, _ = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # n_rbac_authorised = 0 -> recall should be 1.0 (no positives to miss)
    # n_rbac_unauthorised = 2, FP = 0 -> OPR = 0
    assert metrics.recall == 1.0
    assert metrics.under_privilege_rate == 0.0
    assert metrics.over_privilege_rate == 0.0
