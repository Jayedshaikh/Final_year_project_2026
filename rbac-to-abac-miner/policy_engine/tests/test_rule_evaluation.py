"""Unit tests for rule evaluation primitives.

Owner: Granthali (policy_engine module)
"""
import pytest
from shared.schemas.contracts import ABACRule, Condition, Operator, RuleStatus
from policy_engine.schemas.rule import evaluate_condition, rule_matches


class TestEvaluateCondition:
    """Test evaluate_condition for all operators and fail-safe behavior."""
    
    def test_eq_operator_pass(self):
        cond = Condition(attribute="user.department", operator=Operator.EQ, value="HR")
        user_attrs = {"department": "HR"}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_eq_operator_fail(self):
        cond = Condition(attribute="user.department", operator=Operator.EQ, value="HR")
        user_attrs = {"department": "IT"}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_neq_operator_pass(self):
        cond = Condition(attribute="user.department", operator=Operator.NEQ, value="HR")
        user_attrs = {"department": "IT"}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_neq_operator_fail(self):
        cond = Condition(attribute="user.department", operator=Operator.NEQ, value="HR")
        user_attrs = {"department": "HR"}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_in_operator_pass(self):
        cond = Condition(attribute="user.role", operator=Operator.IN, value=["admin", "manager"])
        user_attrs = {"role": "admin"}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_in_operator_fail(self):
        cond = Condition(attribute="user.role", operator=Operator.IN, value=["admin", "manager"])
        user_attrs = {"role": "user"}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_not_in_operator_pass(self):
        cond = Condition(attribute="user.role", operator=Operator.NOT_IN, value=["admin", "manager"])
        user_attrs = {"role": "user"}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_not_in_operator_fail(self):
        cond = Condition(attribute="user.role", operator=Operator.NOT_IN, value=["admin", "manager"])
        user_attrs = {"role": "admin"}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_lte_operator_pass(self):
        cond = Condition(attribute="user.level", operator=Operator.LTE, value=5)
        user_attrs = {"level": 3}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_lte_operator_equal(self):
        cond = Condition(attribute="user.level", operator=Operator.LTE, value=5)
        user_attrs = {"level": 5}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_lte_operator_fail(self):
        cond = Condition(attribute="user.level", operator=Operator.LTE, value=5)
        user_attrs = {"level": 7}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_lt_operator_pass(self):
        cond = Condition(attribute="user.level", operator=Operator.LT, value=5)
        user_attrs = {"level": 3}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_lt_operator_fail_equal(self):
        cond = Condition(attribute="user.level", operator=Operator.LT, value=5)
        user_attrs = {"level": 5}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_gt_operator_pass(self):
        cond = Condition(attribute="user.level", operator=Operator.GT, value=5)
        user_attrs = {"level": 7}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_gt_operator_fail_equal(self):
        cond = Condition(attribute="user.level", operator=Operator.GT, value=5)
        user_attrs = {"level": 5}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_gte_operator_pass(self):
        cond = Condition(attribute="user.level", operator=Operator.GTE, value=5)
        user_attrs = {"level": 7}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_gte_operator_equal(self):
        cond = Condition(attribute="user.level", operator=Operator.GTE, value=5)
        user_attrs = {"level": 5}
        assert evaluate_condition(cond, user_attrs, {}) is True
    
    def test_gte_operator_fail(self):
        cond = Condition(attribute="user.level", operator=Operator.GTE, value=5)
        user_attrs = {"level": 3}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_missing_attribute_returns_false(self):
        cond = Condition(attribute="user.department", operator=Operator.EQ, value="HR")
        user_attrs = {"level": 3}  # department missing
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_none_value_returns_false(self):
        cond = Condition(attribute="user.department", operator=Operator.EQ, value="HR")
        user_attrs = {"department": None}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_type_mismatch_returns_false(self):
        # Comparing string with int should raise exception in comparison, return False
        cond = Condition(attribute="user.level", operator=Operator.LT, value=5)
        user_attrs = {"level": "high"}  # string instead of int
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_unknown_operator_returns_false(self):
        # Create condition with invalid operator by manipulating the value
        cond = Condition(attribute="user.department", operator=Operator.EQ, value="HR")
        cond.operator = "UNKNOWN"  # Force invalid operator
        user_attrs = {"department": "HR"}
        assert evaluate_condition(cond, user_attrs, {}) is False
    
    def test_resource_attribute(self):
        cond = Condition(attribute="resource.type", operator=Operator.EQ, value="document")
        resource_attrs = {"type": "document"}
        assert evaluate_condition(cond, {}, resource_attrs) is True
    
    def test_malformed_attribute_no_prefix(self):
        cond = Condition(attribute="department", operator=Operator.EQ, value="HR")
        user_attrs = {"department": "HR"}
        assert evaluate_condition(cond, user_attrs, {}) is False


class TestRuleMatches:
    """Test rule_matches for various scenarios."""
    
    def test_all_conditions_pass_returns_true(self):
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR"),
                Condition(attribute="user.level", operator=Operator.GTE, value=3)
            ],
            support=0.5,
            confidence=0.9
        )
        user_attrs = {"department": "HR", "level": 5}
        assert rule_matches(rule, user_attrs, {}, "read") is True
    
    def test_one_condition_fails_returns_false(self):
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR"),
                Condition(attribute="user.level", operator=Operator.GTE, value=3)
            ],
            support=0.5,
            confidence=0.9
        )
        user_attrs = {"department": "IT", "level": 5}  # department doesn't match
        assert rule_matches(rule, user_attrs, {}, "read") is False
    
    def test_wrong_action_returns_false(self):
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.5,
            confidence=0.9
        )
        user_attrs = {"department": "HR"}
        assert rule_matches(rule, user_attrs, {}, "write") is False  # action mismatch
    
    def test_empty_conditions_returns_false(self):
        # Cannot create ABACRule with empty conditions due to Pydantic validation,
        # but we can test the fail-safe behavior by creating a rule and clearing conditions
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.5,
            confidence=0.9
        )
        # Manually clear conditions to simulate malformed rule
        rule.conditions = []
        user_attrs = {"department": "HR"}
        assert rule_matches(rule, user_attrs, {}, "read") is False
    
    def test_mixed_user_and_resource_conditions(self):
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR"),
                Condition(attribute="resource.type", operator=Operator.EQ, value="document")
            ],
            support=0.5,
            confidence=0.9
        )
        user_attrs = {"department": "HR"}
        resource_attrs = {"type": "document"}
        assert rule_matches(rule, user_attrs, resource_attrs, "read") is True
