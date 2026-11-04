"""Rule evaluation primitives.

Owner: Granthali (policy_engine module)

Fail-safe design: all functions return False (deny) on missing attributes,
type mismatches, unknown operators, malformed rules, or any exception.
"""
from shared.schemas.contracts import ABACRule, Condition, Operator


def evaluate_condition(cond: Condition, user_attrs: dict, resource_attrs: dict) -> bool:
    """Evaluate a single condition against user and resource attributes.
    
    Fail-safe behavior: returns False (deny) if attribute is missing,
    value is None, types are incompatible, operator is unknown, or any
    exception occurs during evaluation.
    
    Args:
        cond: Condition to evaluate
        user_attrs: User attributes dictionary (keys without 'user.' prefix)
        resource_attrs: Resource attributes dictionary (keys without 'resource.' prefix)
        
    Returns:
        True if condition passes, False otherwise (fail-safe: deny on error)
    """
    try:
        # Extract attribute name and prefix
        attr_name = cond.attribute
        
        # Determine which attribute dictionary to use
        if attr_name.startswith("user."):
            attr_key = attr_name[5:]  # Remove "user." prefix
            attrs = user_attrs
        elif attr_name.startswith("resource."):
            attr_key = attr_name[9:]  # Remove "resource." prefix
            attrs = resource_attrs
        else:
            # Malformed attribute name (no prefix)
            return False
        
        # Check if attribute exists
        if attr_key not in attrs:
            return False
        
        actual_value = attrs[attr_key]
        
        # Deny if value is None
        if actual_value is None:
            return False
        
        expected_value = cond.value

        # Normalise strings to lowercase for case-insensitive comparison
        # (attributes are lowercased during training; rules may have mixed case)
        if isinstance(actual_value, str):
            actual_value = actual_value.lower()
        if isinstance(expected_value, str):
            expected_value = expected_value.lower()
        if isinstance(expected_value, list):
            expected_value = [v.lower() if isinstance(v, str) else v for v in expected_value]
        
        # Evaluate based on operator
        if cond.operator == Operator.EQ:
            return actual_value == expected_value
        elif cond.operator == Operator.NEQ:
            return actual_value != expected_value
        elif cond.operator == Operator.IN:
            # expected_value should be a list
            if not isinstance(expected_value, list):
                return False
            return actual_value in expected_value
        elif cond.operator == Operator.NOT_IN:
            # expected_value should be a list
            if not isinstance(expected_value, list):
                return False
            return actual_value not in expected_value
        elif cond.operator == Operator.LTE:
            return actual_value <= expected_value
        elif cond.operator == Operator.LT:
            return actual_value < expected_value
        elif cond.operator == Operator.GT:
            return actual_value > expected_value
        elif cond.operator == Operator.GTE:
            return actual_value >= expected_value
        else:
            # Unknown operator
            return False
            
    except Exception:
        # Any exception during evaluation: fail-safe deny
        return False


def rule_matches(rule: ABACRule, user_attrs: dict, resource_attrs: dict, action: str) -> bool:
    """Check if a rule matches the given user, resource, and action.
    
    Fail-safe behavior: returns False (deny) if action doesn't match,
    conditions are empty (malformed), any condition fails, or any
    exception occurs during evaluation.
    
    Args:
        rule: ABAC rule to evaluate
        user_attrs: User attributes dictionary (keys without 'user.' prefix)
        resource_attrs: Resource attributes dictionary (keys without 'resource.' prefix)
        action: Action/permission being checked
        
    Returns:
        True if rule matches (all conditions pass), False otherwise (fail-safe: deny on error)
    """
    try:
        # Check action match
        if action != rule.action:
            return False
        
        # Empty conditions is malformed
        if not rule.conditions or len(rule.conditions) == 0:
            return False
        
        # Evaluate all conditions - ALL must pass
        for condition in rule.conditions:
            if not evaluate_condition(condition, user_attrs, resource_attrs):
                return False
        
        # All conditions passed
        return True
        
    except Exception:
        # Any exception during evaluation: fail-safe deny
        return False
