"""Simple tests for WSC to verify it works."""

from shared.schemas.contracts import ABACRule, Condition
from policy_engine.policy_validator.wsc import weighted_structural_complexity


def test_wsc_basic():
    """Basic WSC test."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            support=0.8,
            confidence=0.9,
        )
    ]
    # WSC = 1 (rule) + 1 * 1 (condition) = 2.0
    wsc = weighted_structural_complexity(rules)
    assert wsc == 2.0


def test_wsc_with_in_operator():
    """WSC with 'in' operator."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="in", value=["IT", "HR"])],
            support=0.8,
            confidence=0.9,
        )
    ]
    # WSC = 1 + 1*1 + 0.5*2 = 3.0
    wsc = weighted_structural_complexity(rules)
    assert wsc == 3.0
