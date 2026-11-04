"""Simple export tests."""

import json
import xml.etree.ElementTree as ET
import pytest
from shared.schemas.contracts import ABACRule, Condition
from policy_engine.policy_exporter.exporter import export_policy


def test_export_json_basic():
    """Export to JSON."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            status="approved",
            support=0.8,
            confidence=0.9,
        )
    ]
    
    result = export_policy(rules, fmt="json", policy_id="policy_001")
    policy = json.loads(result)
    
    assert policy["policy_id"] == "policy_001"
    assert len(policy["rules"]) == 1


def test_export_xacml_basic():
    """Export to XACML."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            status="approved",
            support=0.8,
            confidence=0.9,
        )
    ]
    
    result = export_policy(rules, fmt="xacml", policy_id="policy_001")
    root = ET.fromstring(result)
    
    assert root.tag == "Policy"


def test_export_no_approved_raises():
    """No approved rules raises error."""
    rules = [
        ABACRule(
            rule_id="R001",
            action="read",
            conditions=[Condition(attribute="user.dept", operator="==", value="IT")],
            status="candidate",
            support=0.8,
            confidence=0.9,
        )
    ]
    
    with pytest.raises(ValueError, match="no approved rules"):
        export_policy(rules, fmt="json", policy_id="policy_001")
