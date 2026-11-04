"""Simple validation tests."""

import pandas as pd
from shared.schemas.contracts import ABACRule, Condition
from policy_engine.policy_validator.validator import validate_policy


def test_validate_empty_policy():
    """Empty policy denies all."""
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1"],
        "resource_id": ["r1"],
        "permission": ["read"],
        "authorised": [1],
    })
    user_attrs_df = pd.DataFrame({"user_id": ["u1"], "dept": ["IT"]})
    resource_attrs_df = pd.DataFrame({"resource_id": ["r1"], "type": ["server"]})
    
    metrics, _, under_priv = validate_policy(
        [], access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    # Empty policy -> all denied -> under-privileged
    assert metrics.recall == 0.0
    assert len(under_priv) == 1


def test_validate_perfect_match():
    """Perfect policy match."""
    access_matrix_df = pd.DataFrame({
        "user_id": ["u1"],
        "resource_id": ["r1"],
        "permission": ["read"],
        "authorised": [1],
    })
    user_attrs_df = pd.DataFrame({"user_id": ["u1"], "dept": ["IT"]})
    resource_attrs_df = pd.DataFrame({"resource_id": ["r1"], "type": ["server"]})
    
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            status="approved",
            support=1.0,
            confidence=1.0,
        )
    ]
    
    metrics, _, _ = validate_policy(
        rules, access_matrix_df, user_attrs_df, resource_attrs_df
    )
    
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
