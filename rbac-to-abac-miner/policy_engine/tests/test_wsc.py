"""Tests for Weighted Structural Complexity (WSC) computation."""

import pytest
from shared.schemas.contracts import ABACRule, Condition
from policy_engine.policy_validator.wsc import weighted_structural_complexity


def test_wsc_empty_rules():
    """WSC of empty rules list is 0."""
    assert weighted_structural_complexity([]) == 0.0


def test_wsc_single_rule_one_condition():
    """WSC for single rule with one condition."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="==", value="IT"),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # Default weights: w_rule=1, w_cond=1, w_val=0.5
    # WSC = 1 (rule) + 1 * 1 (condition) + 0 (no in/not_in) = 2.0
    wsc = weighted_structural_complexity(rules)
    assert wsc == 2.0


def test_wsc_rule_with_in_operator():
    """WSC accounts for values in 'in' operator."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="in", value=["IT", "HR", "Finance"]),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # WSC = 1 (rule) + 1 * 1 (condition) + 0.5 * 3 (values) = 3.5
    wsc = weighted_structural_complexity(rules)
    assert wsc == 3.5


def test_wsc_multiple_rules():
    """WSC sums across multiple rules."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="==", value="IT"),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        ),
        ABACRule(
            rule_id="R002",
            action="write",
            conditions=[
                Condition(attribute="user.role", operator="==", value="admin"),
                Condition(attribute="resource.type", operator="in", value=["db", "server"]),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        ),
    ]
    
    # R001: 1 + 1*1 + 0 = 2.0
    # R002: 1 + 1*2 + 0.5*2 = 4.0
    # Total: 6.0
    wsc = weighted_structural_complexity(rules)
    assert wsc == 6.0


def test_wsc_custom_weights():
    """WSC with custom weights."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="in", value=["IT", "HR"]),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    custom_weights = {"w_rule": 2.0, "w_cond": 1.5, "w_val": 1.0}
    # WSC = 2.0 (rule) + 1.5 * 1 (condition) + 1.0 * 2 (values) = 5.5
    wsc = weighted_structural_complexity(rules, custom_weights)
    assert wsc == 5.5


def test_wsc_not_in_operator():
    """WSC accounts for values in 'not_in' operator."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.status", operator="not_in", value=["suspended", "banned"]),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # WSC = 1 + 1*1 + 0.5*2 = 3.0
    wsc = weighted_structural_complexity(rules)
    assert wsc == 3.0


def test_wsc_complex_rule():
    """WSC for complex rule with multiple conditions and in/not_in."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="in", value=["IT", "Engineering"]),
                Condition(attribute="user.clearance", operator=">=", value=3),
                Condition(attribute="resource.classification", operator="not_in", value=["top_secret"]),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # WSC = 1 (rule) + 1*3 (conditions) + 0.5*2 (IT,Eng) + 0 (>=) + 0.5*1 (top_secret)
    #     = 1 + 3 + 1.0 + 0.5 = 5.5
    wsc = weighted_structural_complexity(rules)
    assert wsc == 5.5


def test_wsc_zero_conditions():
    """WSC for rule with no conditions."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # WSC = 1 (rule) + 0 (no conditions) = 1.0
    wsc = weighted_structural_complexity(rules)
    assert wsc == 1.0


def test_wsc_in_operator_single_value():
    """WSC handles 'in' operator with single value."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="in", value=["IT"]),
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # WSC = 1 + 1*1 + 0.5*1 = 2.5
    wsc = weighted_structural_complexity(rules)
    assert wsc == 2.5


def test_wsc_in_operator_non_list_value():
    """WSC handles 'in' operator with non-list value (treats as 1 element)."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="in", value="IT"),  # Not a list
            ],
            status="candidate", support=0.8, confidence=0.9,
            source="tree_path",
        )
    ]
    
    # WSC = 1 + 1*1 + 0.5*1 = 2.5
    wsc = weighted_structural_complexity(rules)
    assert wsc == 2.5
