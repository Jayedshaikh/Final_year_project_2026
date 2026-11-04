"""
Policy export to JSON and XACML-style XML formats.

Only approved rules are exported. Raises ValueError if no approved rules exist.
"""

import json
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom

from shared.schemas.contracts import ABACRule


def export_policy(rules: list[ABACRule], fmt: str, policy_id: str) -> str:
    """
    Export ABAC policy in JSON or XACML-style XML format.

    Args:
        rules: List of ABAC rules
        fmt: Export format - "json" or "xacml"
        policy_id: Unique policy identifier

    Returns:
        str: Serialized policy in requested format

    Raises:
        ValueError: If no approved rules exist (cannot export unapproved rules)
        ValueError: If format is not "json" or "xacml"

    Security Rules:
        - ONLY rules with status == "approved" are exported
        - Raises ValueError if no approved rules (never silently export empty policy)
        - Never export rejected, candidate, or un-reviewed rules
        - Default decision is DENY (closed world)

    JSON Format:
        {
          "policy_id": "...",
          "default_decision": "deny",
          "generated_at": "ISO timestamp",
          "rules": [
            {
              "rule_id": "...",
              "effect": "permit",
              "action": "...",
              "conditions": [...],
              "support": float,
              "confidence": float
            }
          ]
        }

    XACML-Style XML:
        <Policy PolicyId="..." RuleCombiningAlgId="permit-overrides">
          <Description>ABAC Policy</Description>
          <Rule RuleId="..." Effect="Permit">
            <Target>...</Target>
            <Condition>...</Condition>
          </Rule>
          ...
          <Rule RuleId="default-deny" Effect="Deny"/>
        </Policy>

    Note: XACML output is "XACML-style" (readable representation),
    not certified XACML 3.0 implementation.
    """
    # Filter approved rules only
    approved_rules = [r for r in rules if r.status == "approved"]

    if not approved_rules:
        raise ValueError(
            "Cannot export policy: no approved rules. "
            "At least one rule must have status='approved'."
        )

    if fmt == "json":
        return _export_json(approved_rules, policy_id)
    elif fmt == "xacml":
        return _export_xacml(approved_rules, policy_id)
    else:
        raise ValueError(
            f"Invalid export format: '{fmt}'. Must be 'json' or 'xacml'."
        )


def _export_json(rules: list[ABACRule], policy_id: str) -> str:
    """Export policy as JSON."""
    policy_dict = {
        "policy_id": policy_id,
        "default_decision": "deny",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "rules": [],
    }

    for rule in rules:
        rule_dict = {
            "rule_id": rule.rule_id,
            "effect": "permit",
            "action": rule.action,
            "conditions": [
                {
                    "attribute": cond.attribute,
                    "operator": cond.operator,
                    "value": cond.value,
                }
                for cond in rule.conditions
            ],
            "support": rule.support if rule.support is not None else 0.0,
            "confidence": rule.confidence if rule.confidence is not None else 0.0,
        }
        policy_dict["rules"].append(rule_dict)

    # Stable key order, pretty-printed
    return json.dumps(policy_dict, indent=2, ensure_ascii=False)


def _export_xacml(rules: list[ABACRule], policy_id: str) -> str:
    """Export policy as XACML-style XML."""
    # Root Policy element
    policy_elem = ET.Element(
        "Policy",
        attrib={
            "PolicyId": policy_id,
            "RuleCombiningAlgId": "urn:oasis:names:tc:xacml:3.0:rule-combining-algorithm:permit-overrides",
            "Version": "1.0",
        },
    )

    # Description
    desc_elem = ET.SubElement(policy_elem, "Description")
    desc_elem.text = "ABAC Policy - Permit rules with default deny"

    # Add permit rules
    for rule in rules:
        rule_elem = ET.SubElement(
            policy_elem,
            "Rule",
            attrib={"RuleId": rule.rule_id, "Effect": "Permit"},
        )

        # Target: action match
        target_elem = ET.SubElement(rule_elem, "Target")
        any_of_elem = ET.SubElement(target_elem, "AnyOf")
        all_of_elem = ET.SubElement(any_of_elem, "AllOf")
        match_elem = ET.SubElement(
            all_of_elem,
            "Match",
            attrib={"MatchId": "urn:oasis:names:tc:xacml:1.0:function:string-equal"},
        )
        attr_value_elem = ET.SubElement(match_elem, "AttributeValue", attrib={"DataType": "http://www.w3.org/2001/XMLSchema#string"})
        attr_value_elem.text = rule.action
        attr_designator_elem = ET.SubElement(
            match_elem,
            "AttributeDesignator",
            attrib={
                "AttributeId": "urn:oasis:names:tc:xacml:1.0:action:action-id",
                "Category": "urn:oasis:names:tc:xacml:3.0:attribute-category:action",
                "DataType": "http://www.w3.org/2001/XMLSchema#string",
                "MustBePresent": "true",
            },
        )

        # Condition: AND all attribute conditions
        if rule.conditions:
            condition_elem = ET.SubElement(rule_elem, "Condition")
            if len(rule.conditions) > 1:
                apply_elem = ET.SubElement(
                    condition_elem,
                    "Apply",
                    attrib={"FunctionId": "urn:oasis:names:tc:xacml:1.0:function:and"},
                )
            else:
                apply_elem = condition_elem

            for cond in rule.conditions:
                # Determine category
                if cond.attribute.startswith("user."):
                    category = "urn:oasis:names:tc:xacml:1.0:subject-category:access-subject"
                    attr_name = cond.attribute[5:]  # strip 'user.'
                elif cond.attribute.startswith("resource."):
                    category = "urn:oasis:names:tc:xacml:3.0:attribute-category:resource"
                    attr_name = cond.attribute[9:]  # strip 'resource.'
                else:
                    # Fallback: treat as resource
                    category = "urn:oasis:names:tc:xacml:3.0:attribute-category:resource"
                    attr_name = cond.attribute

                # Map operator to XACML function
                func_map = {
                    "==": "urn:oasis:names:tc:xacml:1.0:function:string-equal",
                    "!=": "urn:oasis:names:tc:xacml:1.0:function:string-not-equal",
                    "in": "urn:oasis:names:tc:xacml:1.0:function:string-is-in",
                    "not_in": "urn:oasis:names:tc:xacml:1.0:function:string-not-in",
                    "<=": "urn:oasis:names:tc:xacml:1.0:function:integer-less-than-or-equal",
                    "<": "urn:oasis:names:tc:xacml:1.0:function:integer-less-than",
                    ">": "urn:oasis:names:tc:xacml:1.0:function:integer-greater-than",
                    ">=": "urn:oasis:names:tc:xacml:1.0:function:integer-greater-than-or-equal",
                }
                func_id = func_map.get(cond.operator, "urn:oasis:names:tc:xacml:1.0:function:string-equal")

                # Build comparison
                comp_elem = ET.SubElement(apply_elem, "Apply", attrib={"FunctionId": func_id})
                
                # AttributeValue
                value_str = str(cond.value) if not isinstance(cond.value, list) else ",".join(map(str, cond.value))
                attr_val_elem = ET.SubElement(comp_elem, "AttributeValue", attrib={"DataType": "http://www.w3.org/2001/XMLSchema#string"})
                attr_val_elem.text = value_str
                
                # AttributeDesignator
                attr_des_elem = ET.SubElement(
                    comp_elem,
                    "AttributeDesignator",
                    attrib={
                        "AttributeId": f"urn:abac:{attr_name}",
                        "Category": category,
                        "DataType": "http://www.w3.org/2001/XMLSchema#string",
                        "MustBePresent": "true",
                    },
                )

    # Default deny rule
    deny_rule_elem = ET.SubElement(
        policy_elem,
        "Rule",
        attrib={"RuleId": "default-deny", "Effect": "Deny"},
    )
    deny_desc_elem = ET.SubElement(deny_rule_elem, "Description")
    deny_desc_elem.text = "Default deny rule"

    # Pretty-print XML
    rough_string = ET.tostring(policy_elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
