"""Tests for policy export to JSON and XACML formats."""

import json
import xml.etree.ElementTree as ET
import pytest
from shared.schemas.contracts import ABACRule, Condition
from policy_engine.policy_exporter.exporter import export_policy


def test_export_json_format():
    """Export approved rules to JSON format."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[
                Condition(attribute="user.dept", operator="==", value="IT"),
                Condition(attribute="resource.type", operator="in", value=["server", "db"]),
            ],
            status="approved",
            source="tree_path",
            support=0.8,
            confidence=0.9,
        )
    ]
    
    result = export_policy(rules, fmt="json", policy_id="policy_001")
    
    # Parse JSON
    policy = json.loads(result)
    
    assert policy["policy_id"] == "policy_001"
    assert policy["default_decision"] == "deny"
    assert "generated_at" in policy
    assert len(policy["rules"]) == 1
    
    rule = policy["rules"][0]
    assert rule["rule_id"] == "R001"
    assert rule["effect"] == "permit"
    assert rule["action"] == "read"
    assert len(rule["conditions"]) == 2
    assert rule["support"] == 0.8
    assert rule["confidence"] == 0.9


def test_export_xacml_format():
    """Export approved rules to XACML-style XML format."""
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
    
    result = export_policy(rules, fmt="xacml", policy_id="policy_001")
    
    # Parse XML
    root = ET.fromstring(result)
    
    assert root.tag == "Policy"
    assert root.attrib["PolicyId"] == "policy_001"
    assert "permit-overrides" in root.attrib["RuleCombiningAlgId"]
    
    # Should have at least 2 rules: 1 permit + 1 default deny
    rules_elem = root.findall("Rule")
    assert len(rules_elem) >= 2
    
    # Check first rule is permit
    assert rules_elem[0].attrib["RuleId"] == "R001"
    assert rules_elem[0].attrib["Effect"] == "Permit"
    
    # Check last rule is default deny
    assert rules_elem[-1].attrib["Effect"] == "Deny"


def test_export_raises_on_no_approved_rules():
    """Raise ValueError if no approved rules exist."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[],
            status="candidate",  # Not approved
            source="tree_path",
        )
    ]
    
    with pytest.raises(ValueError, match="no approved rules"):
        export_policy(rules, fmt="json", policy_id="policy_001")


def test_export_only_includes_approved_rules():
    """Only approved rules should be exported."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[],
            status="approved",
            source="tree_path",
        ),
        ABACRule(
            rule_id="R002",
            action="write",
            conditions=[],
            status="rejected",  # Should not be exported
            source="tree_path",
        ),
        ABACRule(
            rule_id="R003",
            action="delete",
            conditions=[],
            status="candidate",  # Should not be exported
            source="tree_path",
        ),
    ]
    
    result = export_policy(rules, fmt="json", policy_id="policy_001")
    policy = json.loads(result)
    
    # Only R001 (approved) should be exported
    assert len(policy["rules"]) == 1
    assert policy["rules"][0]["rule_id"] == "R001"


def test_export_invalid_format_raises():
    """Raise ValueError for invalid format."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[],
            status="approved",
            source="tree_path",
        )
    ]
    
    with pytest.raises(ValueError, match="Invalid export format"):
        export_policy(rules, fmt="yaml", policy_id="policy_001")


def test_export_json_multiple_rules():
    """Export multiple approved rules."""
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
            action="write",
            conditions=[Condition(attribute="user.role", operator="==", value="admin")],
            status="approved",
            source="merged", support=0.8, confidence=0.9,
            derived_from=["R003", "R004"],
        ),
    ]
    
    result = export_policy(rules, fmt="json", policy_id="policy_002")
    policy = json.loads(result)
    
    assert len(policy["rules"]) == 2
    assert policy["rules"][0]["rule_id"] == "R001"
    assert policy["rules"][1]["rule_id"] == "R002"


def test_export_xacml_parses_correctly():
    """Exported XACML should be valid XML."""
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
        )
    ]
    
    result = export_policy(rules, fmt="xacml", policy_id="policy_001")
    
    # Should parse without error
    root = ET.fromstring(result)
    assert root is not None
    
    # Verify structure
    policy_elem = root
    assert policy_elem.tag == "Policy"
    
    desc = policy_elem.find("Description")
    assert desc is not None
    
    rules_elem = policy_elem.findall("Rule")
    assert len(rules_elem) >= 2  # At least 1 permit + 1 deny


def test_export_handles_none_support_confidence():
    """Export should handle None support/confidence gracefully."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[],
            status="approved",
            source="tree_path",
            support=None,
            confidence=None,
        )
    ]
    
    result = export_policy(rules, fmt="json", policy_id="policy_001")
    policy = json.loads(result)
    
    # Should default to 0.0
    assert policy["rules"][0]["support"] == 0.0
    assert policy["rules"][0]["confidence"] == 0.0
