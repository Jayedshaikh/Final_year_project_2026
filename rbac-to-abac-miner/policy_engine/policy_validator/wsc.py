"""
Weighted Structural Complexity (WSC) computation.

WSC quantifies policy complexity by weighting rules, conditions, and values.
Default formula: WSC = sum(w_rule + w_cond * n_conditions + w_val * total_in_set_elements)
"""

from shared.schemas.contracts import ABACRule


def weighted_structural_complexity(
    rules: list[ABACRule], weights: dict[str, float] | None = None
) -> float:
    """
    Compute Weighted Structural Complexity for a set of rules.

    Args:
        rules: List of ABAC rules to evaluate
        weights: Optional custom weights dict with keys:
            - w_rule: Weight per rule (default 1.0)
            - w_cond: Weight per condition (default 1.0)
            - w_val: Weight per value in in/not_in sets (default 0.5)

    Returns:
        float: Total WSC score (>= 0.0)

    Formula:
        For each rule: w_rule + w_cond * n_conditions + w_val * total_in_set_values
        Sum across all rules.

    Implementation Decision (D-002):
        Default weights chosen for balanced complexity measurement.
        Configurable via config/mining_config.json -> wsc_weights.
    """
    # Default weights
    default_weights = {"w_rule": 1.0, "w_cond": 1.0, "w_val": 0.5}
    w = weights if weights is not None else default_weights

    w_rule = w.get("w_rule", 1.0)
    w_cond = w.get("w_cond", 1.0)
    w_val = w.get("w_val", 0.5)

    total_wsc = 0.0

    for rule in rules:
        # Base weight for having a rule
        rule_wsc = w_rule

        # Weight for conditions
        n_conditions = len(rule.conditions)
        rule_wsc += w_cond * n_conditions

        # Weight for values in 'in' and 'not_in' sets
        for condition in rule.conditions:
            if condition.operator in ("in", "not_in"):
                # value should be a list for in/not_in operators
                if isinstance(condition.value, list):
                    rule_wsc += w_val * len(condition.value)
                else:
                    # Single value treated as 1 element
                    rule_wsc += w_val

        total_wsc += rule_wsc

    return total_wsc
