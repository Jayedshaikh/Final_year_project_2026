"""Unit tests for rule_pruner module.

Owner: Granthali (policy_engine module)

Tests pruning of low-support and redundant rules:
- Low-support rules dropped
- Redundant rules dropped (positives covered by others)
- Idempotence: prune(prune(X)) == prune(X)
- Empty input returns empty output
"""
import pandas as pd
import pytest
from shared.schemas.contracts import ABACRule, Condition, Operator
from policy_engine.schemas.config import OptimisationConfig
from policy_engine.rule_pruner import prune_rules


def test_prune_low_support_rule():
    """Test that rules below min_support threshold are pruned."""
    rule1 = ABACRule(
        rule_id="R001",
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
    
    # This rule matches very few samples (low support)
    rule2 = ABACRule(
        rule_id="R002",
        effect="permit",
        action="write",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="rare_role")
        ],
        support=0.05,  # Low support
        confidence=0.9,
        status="candidate",
        source="tree_path"
    )
    
    # rule2 matches only 1 out of 20 samples = 0.05 support (below 0.1 threshold)
    samples = pd.DataFrame({
        'user_id': ['u' + str(i) for i in range(1, 21)],
        'resource_id': ['r1'] * 20,
        'permission': ['read'] * 10 + ['write'] * 10,
        'user.role': ['admin'] * 10 + ['rare_role'] + ['user'] * 9,
        'authorised': [1] * 10 + [1] + [0] * 9
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([rule1, rule2], samples, cfg)
    
    # rule2 should be pruned (support = 1/20 = 0.05 < 0.1)
    assert count == 1
    assert len(pruned) == 1
    # rule1 should remain (support = 10/20 = 0.5)
    rule_ids = [r.rule_id for r in pruned]
    assert "R001" in rule_ids
    assert "R002" not in rule_ids


def test_prune_redundant_rule():
    """Test that redundant rules (positives covered by others) are pruned."""
    # rule1 matches admin role
    rule1 = ABACRule(
        rule_id="R003",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="admin")
        ],
        support=0.5,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    # rule2 is more specific (admin + department) - redundant
    rule2 = ABACRule(
        rule_id="R004",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="admin"),
            Condition(attribute="user.department", operator=Operator.EQ, value="IT")
        ],
        support=0.3,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4'],
        'resource_id': ['r1', 'r1', 'r1', 'r1'],
        'permission': ['access', 'access', 'access', 'access'],
        'user.role': ['admin', 'admin', 'user', 'admin'],
        'user.department': ['IT', 'Sales', 'IT', 'IT'],
        'authorised': [1, 1, 0, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([rule1, rule2], samples, cfg)
    
    # rule2 should be pruned as redundant (its positives are covered by rule1)
    assert count >= 1
    assert len(pruned) == 1
    assert pruned[0].rule_id == "R003"


def test_idempotence():
    """Test that prune(prune(rules)) == prune(rules)."""
    rule1 = ABACRule(
        rule_id="R005",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.level", operator=Operator.GTE, value=2)
        ],
        support=0.6,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R006",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.level", operator=Operator.GTE, value=3)
        ],
        support=0.4,
        confidence=0.95,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4', 'u5'],
        'resource_id': ['r1'] * 5,
        'permission': ['read'] * 5,
        'user.level': [2, 3, 4, 1, 5],
        'authorised': [1, 1, 1, 0, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    # First pruning
    pruned1, count1 = prune_rules([rule1, rule2], samples, cfg)
    
    # Second pruning
    pruned2, count2 = prune_rules(pruned1, samples, cfg)
    
    # Should be idempotent
    assert len(pruned1) == len(pruned2)
    assert set(r.rule_id for r in pruned1) == set(r.rule_id for r in pruned2)
    assert count2 == 0  # No additional rules pruned


def test_empty_input_returns_empty_output():
    """Test that empty rules list returns empty result."""
    samples = pd.DataFrame({
        'user_id': [],
        'resource_id': [],
        'permission': [],
        'authorised': []
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([], samples, cfg)
    
    assert count == 0
    assert len(pruned) == 0


def test_prune_rule_matching_no_positives():
    """Test that rules matching no positives are pruned as redundant."""
    rule1 = ABACRule(
        rule_id="R007",
        effect="permit",
        action="delete",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="nonexistent")
        ],
        support=0.0,
        confidence=0.0,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R008",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.role", operator=Operator.EQ, value="reader")
        ],
        support=0.5,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2'],
        'resource_id': ['r1', 'r1'],
        'permission': ['read', 'read'],
        'user.role': ['reader', 'reader'],
        'authorised': [1, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([rule1, rule2], samples, cfg)
    
    # rule1 should be pruned (matches no positives, low support)
    assert count >= 1
    rule_ids = [r.rule_id for r in pruned]
    assert "R008" in rule_ids
    # R007 might be pruned for low support or redundancy


def test_keep_non_redundant_rules():
    """Test that non-redundant rules are all kept."""
    # Three rules covering different positives
    rule1 = ABACRule(
        rule_id="R009",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.department", operator=Operator.EQ, value="Sales")
        ],
        support=0.3,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    rule2 = ABACRule(
        rule_id="R010",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.department", operator=Operator.EQ, value="IT")
        ],
        support=0.3,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    rule3 = ABACRule(
        rule_id="R011",
        effect="permit",
        action="access",
        conditions=[
            Condition(attribute="user.department", operator=Operator.EQ, value="HR")
        ],
        support=0.3,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4'],
        'resource_id': ['r1'] * 4,
        'permission': ['access'] * 4,
        'user.department': ['Sales', 'IT', 'HR', 'Finance'],
        'authorised': [1, 1, 1, 0]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([rule1, rule2, rule3], samples, cfg)
    
    # All rules should be kept (each covers unique positives)
    assert len(pruned) == 3
    assert count == 0


def test_prune_with_partial_overlap():
    """Test pruning when rules have partial overlap in matched positives."""
    # rule1: user.level >= 2
    rule1 = ABACRule(
        rule_id="R012",
        effect="permit",
        action="view",
        conditions=[
            Condition(attribute="user.level", operator=Operator.GTE, value=2)
        ],
        support=0.6,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    # rule2: user.level >= 3 (subset of rule1)
    rule2 = ABACRule(
        rule_id="R013",
        effect="permit",
        action="view",
        conditions=[
            Condition(attribute="user.level", operator=Operator.GTE, value=3)
        ],
        support=0.4,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4', 'u5'],
        'resource_id': ['r1'] * 5,
        'permission': ['view'] * 5,
        'user.level': [1, 2, 3, 4, 5],
        'authorised': [0, 1, 1, 1, 1]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([rule1, rule2], samples, cfg)
    
    # rule2 should be pruned as redundant (its positives {3,4,5} are covered by rule1 {2,3,4,5})
    assert len(pruned) == 1
    assert pruned[0].rule_id == "R012"
    assert count == 1


def test_single_rule_not_pruned():
    """Test that a single rule with sufficient support is not pruned."""
    rule = ABACRule(
        rule_id="R014",
        effect="permit",
        action="read",
        conditions=[
            Condition(attribute="user.active", operator=Operator.EQ, value=True)
        ],
        support=0.8,
        confidence=1.0,
        status="candidate",
        source="tree_path"
    )
    
    samples = pd.DataFrame({
        'user_id': ['u1', 'u2', 'u3', 'u4', 'u5'],
        'resource_id': ['r1'] * 5,
        'permission': ['read'] * 5,
        'user.active': [True, True, True, True, False],
        'authorised': [1, 1, 1, 1, 0]
    })
    
    cfg = OptimisationConfig(min_support=0.1, min_confidence=0.8)
    
    pruned, count = prune_rules([rule], samples, cfg)
    
    assert len(pruned) == 1
    assert pruned[0].rule_id == "R014"
    assert count == 0
