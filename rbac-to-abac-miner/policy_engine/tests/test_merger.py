"""Unit tests for rule_merger module.

Owner: Granthali (policy_engine module)

Tests merging of rules differing in one condition:
- == conditions merged into 'in' set
- Numeric thresholds widened
- Conflicting merges refused
- Confidence threshold checked
- derived_from and source fields populated correctly
"""
import pandas as pd
import pytest
from shared.schemas.contracts import ABACRule, Condition, Operator
from policy_engine.schemas.config import OptimisationConfig
from policy_engine.rule_merger import merge_rules


def test_merge_two_eq_conditions_into_in_set():
    """Test merging two == conditions on same attribute into 'in' set."""
    # Two rules identical except for one attribute value
    rule1 = ABACRule(
        rule_id="R001",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.department", operator=Operator.EQ, value="sales"),
            Condition(attribute="resource.type", operator=Operator.EQ, value="report")
        ],
        support=0.5,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R002",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.department", operator=Operator.EQ, value="marketing"),
            Condition(attribute="resource.type", operator=Operator.EQ, value="report")
        ],
        support=0.5,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    # Sample data
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4'],
        'resource_id': ['r1', 'r1', 'r1', 'r1'],
        'permission': ['read', 'read', 'read', 'read'],
        'user.department': ['sales', 'marketing', 'engineering', 'sales'],
        'resource.type': ['report', 'report', 'report', 'document'],
        'authorised': [1, 1, 0, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8, confidence_tolerance=0.1)
    
    merged, count = merge_rules([rule1, rule2], samples, cfg)
    
    # Should have merged into one rule
    assert count == 1
    assert len(merged) == 1
    
    merged_rule = merged[0]
    assert merged_rule.source == "merged"
    assert set(merged_rule.derived_from) == {"R001", "R002"}
    assert merged_rule.status == "optimised"
    assert merged_rule.rule_id.startswith("M")
    
    # Check conditions
    assert len(merged_rule.conditions) == 2
    
    # Find the merged condition
    dept_cond = [c for c in merged_rule.conditions if c.attribute == "user.department"][0]
    assert dept_cond.operator == Operator.IN
    assert set(dept_cond.value) == {"sales", "marketing"}
    
    type_cond = [c for c in merged_rule.conditions if c.attribute == "resource.type"][0]
    assert type_cond.operator == Operator.EQ
    assert type_cond.value == "report"


def test_merge_numeric_thresholds_gte():
    """Test merging numeric >= thresholds (keep smaller/looser bound)."""
    rule1 = ABACRule(
        rule_id="R003",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.age", operator=Operator.GTE, value=18),
            Condition(attribute="resource.type", operator=Operator.EQ, value="content")
        ],
        support=0.4,
        confidence=0.9,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R004",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.age", operator=Operator.GTE, value=21),
            Condition(attribute="resource.type", operator=Operator.EQ, value="content")
        ],
        support=0.3,
        confidence=0.9,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3'],
        'resource_id': ['r1', 'r1', 'r1'],
        'permission': ['access', 'access', 'access'],
        'user.age': [18, 21, 25],
        'resource.type': ['content', 'content', 'content'],
        'authorised': [1, 1, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8, confidence_tolerance=0.1)
    
    merged, count = merge_rules([rule1, rule2], samples, cfg)
    
    assert count == 1
    assert len(merged) == 1
    
    merged_rule = merged[0]
    age_cond = [c for c in merged_rule.conditions if c.attribute == "user.age"][0]
    assert age_cond.operator == Operator.GTE
    assert age_cond.value == 18  # Looser bound (smaller)


def test_merge_numeric_thresholds_lte():
    """Test merging numeric <= thresholds (keep larger/looser bound)."""
    rule1 = ABACRule(
        rule_id="R005",
        effect="permit",
        action="view",
        conditions=[
            Condition(attribute="resource.sensitivity", operator=Operator.LTE, value=3),
            Condition(attribute="user.role", operator=Operator.EQ, value="viewer")
        ],
        support=0.4,
        confidence=0.9,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R006",
        effect="permit",
        action="view",
        conditions=[
            Condition(attribute="resource.sensitivity", operator=Operator.LTE, value=5),
            Condition(attribute="user.role", operator=Operator.EQ, value="viewer")
        ],
        support=0.3,
        confidence=0.9,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2'],
        'resource_id': ['r1', 'r2'],
        'permission': ['view', 'view'],
        'resource.sensitivity': [3, 5],
        'user.role': ['viewer', 'viewer'],
        'authorised': [1, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8, confidence_tolerance=0.1)
    
    merged, count = merge_rules([rule1, rule2], samples, cfg)
    
    assert count == 1
    merged_rule = merged[0]
    sens_cond = [c for c in merged_rule.conditions if c.attribute == "resource.sensitivity"][0]
    assert sens_cond.operator == Operator.LTE
    assert sens_cond.value == 5  # Looser bound (larger)


def test_conflicting_merge_refused_different_actions():
    """Test that rules with different actions are not merged."""
    rule1 = ABACRule(
        rule_id="R007",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="admin")
        ],
        support=0.5,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R008",
        effect="permit",
        action="write",  # Different action
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="admin")
        ],
        support=0.5,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1'],
        'resource_id': ['r1'],
        'permission': ['read'],
        'user.role': ['admin'],
        'authorised': [1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.9)
    
    merged, count = merge_rules([rule1, rule2], samples, cfg)
    
    # Should not merge
    assert count == 0
    assert len(merged) == 2  # Both rules kept unchanged


def test_merge_refused_confidence_below_threshold():
    """Test that merge is refused when confidence drops below threshold."""
    rule1 = ABACRule(
        rule_id="R009",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.clearance", operator=Operator.EQ, value="high"),
            Condition(attribute="resource.type", operator=Operator.EQ, value="secret")
        ],
        support=0.3,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R010",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.clearance", operator=Operator.EQ, value="low"),
            Condition(attribute="resource.type", operator=Operator.EQ, value="secret")
        ],
        support=0.1,
        confidence=0.6,  # Lower confidence
        status="candidate",
        source="tree_path"
    )
    
    # Sample data where merging would create low confidence
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4'],
        'resource_id': ['r1', 'r1', 'r1', 'r1'],
        'permission': ['read', 'read', 'read', 'read'],
        'user.clearance': ['high', 'low', 'low', 'low'],
        'resource.type': ['secret', 'secret', 'secret', 'secret'],
        'authorised': [1, 0, 0, 1]  # Only high clearance authorised mostly
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.9, confidence_tolerance=0.05)
    
    merged, count = merge_rules([rule1, rule2], samples, cfg)
    
    # Should not merge due to low confidence
    assert count == 0
    assert len(merged) == 2


def test_derived_from_populated():
    """Test that derived_from field contains both parent rule IDs."""
    rule1 = ABACRule(
        rule_id="R011",
        effect="permit",
        action="edit",
        conditions=[
            Condition(attribute="user.status", operator=Operator.EQ, value="active")
        ],
        support=0.5,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R012",
        effect="permit",
        action="edit",
        conditions=[
            Condition(attribute="user.status", operator=Operator.EQ, value="pending")
        ],
        support=0.3,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2'],
        'resource_id': ['r1', 'r1'],
        'permission': ['edit', 'edit'],
        'user.status': ['active', 'pending'],
        'authorised': [1, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.9)
    
    merged, count = merge_rules([rule1, rule2], samples, cfg)
    
    assert count == 1
    merged_rule = merged[0]
    assert "R011" in merged_rule.derived_from
    assert "R012" in merged_rule.derived_from
    assert len(merged_rule.derived_from) == 2


def test_merge_empty_rules_list():
    """Test that empty rules list returns empty result."""
    samples = pd.DataFrame({
        'user_id': [],
        'resource_id': [],
        'permission': [],
        'authorised': []
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.9)
    
    merged, count = merge_rules([], samples, cfg)
    
    assert count == 0
    assert len(merged) == 0


def test_merge_single_rule():
    """Test that single rule cannot be merged."""
    rule1 = ABACRule(
        rule_id="R013",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="user")
        ],
        support=0.5,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1'],
        'resource_id': ['r1'],
        'permission': ['read'],
        'user.role': ['user'],
        'authorised': [1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.9)
    
    merged, count = merge_rules([rule1], samples, cfg)
    
    assert count == 0
    assert len(merged) == 1
    assert merged[0].rule_id == "R013"
