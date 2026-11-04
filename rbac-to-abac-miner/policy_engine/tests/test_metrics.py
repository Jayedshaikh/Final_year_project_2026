"""Unit tests for support and confidence metrics.

Owner: Granthali (policy_engine module)

Hand-computed examples with 10-row samples and 2 rules.
"""
import pytest
import pandas as pd
from shared.schemas.contracts import ABACRule, Condition, Operator
from policy_engine.schemas.metrics import support, confidence


class TestSupport:
    """Test support metric computation."""
    
    def test_support_with_hand_computed_example(self):
        """Hand-computed: 10 samples, rule matches 4 -> support = 0.4"""
        # Rule: user.department == "HR" AND action == "read"
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,  # will be computed
            confidence=0.0
        )
        
        # 10 samples: 4 with HR+read, 3 with IT+read, 2 with HR+write, 1 with IT+write
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U3", "resource_id": "R3", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U4", "resource_id": "R4", "permission": "read", "user.department": "HR", "authorised": 0},
            {"user_id": "U5", "resource_id": "R5", "permission": "read", "user.department": "IT", "authorised": 1},
            {"user_id": "U6", "resource_id": "R6", "permission": "read", "user.department": "IT", "authorised": 1},
            {"user_id": "U7", "resource_id": "R7", "permission": "read", "user.department": "IT", "authorised": 0},
            {"user_id": "U8", "resource_id": "R8", "permission": "write", "user.department": "HR", "authorised": 1},
            {"user_id": "U9", "resource_id": "R9", "permission": "write", "user.department": "HR", "authorised": 0},
            {"user_id": "U10", "resource_id": "R10", "permission": "write", "user.department": "IT", "authorised": 1}
        ])
        
        # Rule matches: HR + read -> 4 rows (U1, U2, U3, U4)
        # Support = 4 / 10 = 0.4
        result = support(rule, samples)
        assert result == pytest.approx(0.4)
    
    def test_support_zero_rows(self):
        """Empty samples should return 0.0 (avoid division by zero)."""
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        samples = pd.DataFrame(columns=["user_id", "resource_id", "permission", "user.department", "authorised"])
        
        result = support(rule, samples)
        assert result == 0.0
    
    def test_support_no_matches(self):
        """Rule matching nothing should return 0.0."""
        rule = ABACRule(
            rule_id="R1",
            action="delete",  # no delete actions in samples
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "IT", "authorised": 1}
        ])
        
        result = support(rule, samples)
        assert result == 0.0


class TestConfidence:
    """Test confidence metric computation."""
    
    def test_confidence_with_hand_computed_example(self):
        """Hand-computed: rule matches 4 rows, 3 are positive -> confidence = 0.75"""
        # Rule: user.department == "HR" AND action == "read"
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        # 10 samples, rule matches 4 (HR + read), 3 have authorised=1, 1 has authorised=0
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U3", "resource_id": "R3", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U4", "resource_id": "R4", "permission": "read", "user.department": "HR", "authorised": 0},
            {"user_id": "U5", "resource_id": "R5", "permission": "read", "user.department": "IT", "authorised": 1},
            {"user_id": "U6", "resource_id": "R6", "permission": "read", "user.department": "IT", "authorised": 1},
            {"user_id": "U7", "resource_id": "R7", "permission": "read", "user.department": "IT", "authorised": 0},
            {"user_id": "U8", "resource_id": "R8", "permission": "write", "user.department": "HR", "authorised": 1},
            {"user_id": "U9", "resource_id": "R9", "permission": "write", "user.department": "HR", "authorised": 0},
            {"user_id": "U10", "resource_id": "R10", "permission": "write", "user.department": "IT", "authorised": 1}
        ])
        
        # Rule matches: HR + read -> 4 rows (U1, U2, U3, U4)
        # Positives: 3 (U1, U2, U3)
        # Confidence = 3 / 4 = 0.75
        result = confidence(rule, samples)
        assert result == pytest.approx(0.75)
    
    def test_confidence_all_positives(self):
        """All matched rows are positive -> confidence = 1.0"""
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "HR", "authorised": 1}
        ])
        
        result = confidence(rule, samples)
        assert result == 1.0
    
    def test_confidence_all_negatives(self):
        """All matched rows are negative -> confidence = 0.0"""
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "authorised": 0},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "HR", "authorised": 0}
        ])
        
        result = confidence(rule, samples)
        assert result == 0.0
    
    def test_confidence_zero_rows(self):
        """Empty samples should return 0.0."""
        rule = ABACRule(
            rule_id="R1",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        samples = pd.DataFrame(columns=["user_id", "resource_id", "permission", "user.department", "authorised"])
        
        result = confidence(rule, samples)
        assert result == 0.0
    
    def test_confidence_no_matches(self):
        """Rule matching nothing should return 0.0."""
        rule = ABACRule(
            rule_id="R1",
            action="delete",  # no delete actions in samples
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR")
            ],
            support=0.0,
            confidence=0.0
        )
        
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "authorised": 1},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "IT", "authorised": 1}
        ])
        
        result = confidence(rule, samples)
        assert result == 0.0


class TestBothMetrics:
    """Test both metrics together with complex rules."""
    
    def test_complex_rule_with_multiple_conditions(self):
        """Rule with multiple conditions."""
        # Rule: user.department == "HR" AND user.level >= 3 AND action == "read"
        rule = ABACRule(
            rule_id="R2",
            action="read",
            conditions=[
                Condition(attribute="user.department", operator=Operator.EQ, value="HR"),
                Condition(attribute="user.level", operator=Operator.GTE, value=3)
            ],
            support=0.0,
            confidence=0.0
        )
        
        # 8 samples
        samples = pd.DataFrame([
            {"user_id": "U1", "resource_id": "R1", "permission": "read", "user.department": "HR", "user.level": 5, "authorised": 1},
            {"user_id": "U2", "resource_id": "R2", "permission": "read", "user.department": "HR", "user.level": 3, "authorised": 1},
            {"user_id": "U3", "resource_id": "R3", "permission": "read", "user.department": "HR", "user.level": 2, "authorised": 1},  # level < 3, no match
            {"user_id": "U4", "resource_id": "R4", "permission": "read", "user.department": "IT", "user.level": 5, "authorised": 1},  # not HR, no match
            {"user_id": "U5", "resource_id": "R5", "permission": "read", "user.department": "HR", "user.level": 4, "authorised": 0},  # matches, negative
            {"user_id": "U6", "resource_id": "R6", "permission": "write", "user.department": "HR", "user.level": 5, "authorised": 1},  # wrong action, no match
            {"user_id": "U7", "resource_id": "R7", "permission": "read", "user.department": "HR", "user.level": 3, "authorised": 1},
            {"user_id": "U8", "resource_id": "R8", "permission": "read", "user.department": "Finance", "user.level": 5, "authorised": 0}  # not HR, no match
        ])
        
        # Matches: U1 (pos), U2 (pos), U5 (neg), U7 (pos) -> 4 matches
        # Support = 4 / 8 = 0.5
        supp = support(rule, samples)
        assert supp == pytest.approx(0.5)
        
        # Positives: U1, U2, U7 -> 3 out of 4 matches
        # Confidence = 3 / 4 = 0.75
        conf = confidence(rule, samples)
        assert conf == pytest.approx(0.75)
