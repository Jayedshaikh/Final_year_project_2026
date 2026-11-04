"""Rule merger: merge rules differing in one condition.

Owner: Granthali (policy_engine module)

Evidence-based merging: two rules with the same action and identical conditions
except for one attribute are merged (== values into 'in' set, numeric thresholds
widened). Accept only if merged confidence meets threshold.
"""
import pandas as pd
from typing import List, Tuple
from shared.schemas.contracts import ABACRule, Condition, Operator
from policy_engine.schemas.config import OptimisationConfig
from policy_engine.schemas.metrics import confidence


def merge_rules(rules: List[ABACRule], samples: pd.DataFrame, cfg: OptimisationConfig) -> Tuple[List[ABACRule], int]:
    """Merge rules that differ in only one condition.
    
    Merging criteria:
    - Same action
    - Identical conditions except for one attribute
    - For ==: merge values into 'in' set
    - For numeric comparisons: widen thresholds to looser bound
    - Accept only if merged confidence >= cfg.min_confidence - cfg.confidence_tolerance
    
    Merged rules get:
    - source='merged'
    - derived_from=[parent rule_ids]
    - status='optimised'
    - new rule_id like 'M001', 'M002', ...
    
    Args:
        rules: List of ABAC rules to merge
        samples: DataFrame with access tuples and attributes for validation
        cfg: Optimisation configuration with min_confidence and confidence_tolerance
        
    Returns:
        Tuple of (merged_rules + surviving_originals, n_merged_count)
    """
    try:
        if len(rules) == 0:
            return ([], 0)
        
        merged_rules = []
        merged_count = 0
        used_indices = set()
        merge_id_counter = 1
        
        # Try to merge each pair of rules
        for i in range(len(rules)):
            if i in used_indices:
                continue
            
            rule_i = rules[i]
            merged_this_round = False
            
            for j in range(i + 1, len(rules)):
                if j in used_indices:
                    continue
                
                rule_j = rules[j]
                
                # Check if rules can be merged
                merged_rule = _try_merge_pair(rule_i, rule_j, samples, cfg, f"M{merge_id_counter:03d}")
                
                if merged_rule is not None:
                    # Successful merge
                    merged_rules.append(merged_rule)
                    used_indices.add(i)
                    used_indices.add(j)
                    merged_count += 1
                    merge_id_counter += 1
                    merged_this_round = True
                    break
            
            # If rule_i was not merged, keep it as is
            if not merged_this_round and i not in used_indices:
                merged_rules.append(rule_i)
        
        # Add any remaining unmerged rules
        for idx, rule in enumerate(rules):
            if idx not in used_indices and rule not in merged_rules:
                merged_rules.append(rule)
        
        return (merged_rules, merged_count)
        
    except Exception:
        # Fail-safe: return original rules unchanged on any error
        return (rules, 0)


def _try_merge_pair(rule1: ABACRule, rule2: ABACRule, samples: pd.DataFrame, 
                    cfg: OptimisationConfig, new_rule_id: str) -> ABACRule | None:
    """Try to merge two rules. Returns merged rule if successful, None otherwise.
    
    Args:
        rule1: First rule
        rule2: Second rule
        samples: DataFrame for confidence validation
        cfg: Optimisation configuration
        new_rule_id: ID for the new merged rule
        
    Returns:
        Merged rule if successful, None if merge is not possible or fails validation
    """
    try:
        # Must have same action
        if rule1.action != rule2.action:
            return None
        
        # Must have same number of conditions
        if len(rule1.conditions) != len(rule2.conditions):
            return None
        
        # Sort conditions by attribute name for comparison
        conds1 = sorted(rule1.conditions, key=lambda c: c.attribute)
        conds2 = sorted(rule2.conditions, key=lambda c: c.attribute)
        
        # Find conditions that differ
        differing_indices = []
        for idx, (c1, c2) in enumerate(zip(conds1, conds2)):
            if c1.attribute != c2.attribute or c1.operator != c2.operator or c1.value != c2.value:
                differing_indices.append(idx)
        
        # Must differ in exactly one condition
        if len(differing_indices) != 1:
            return None
        
        diff_idx = differing_indices[0]
        cond1 = conds1[diff_idx]
        cond2 = conds2[diff_idx]
        
        # Must have same attribute
        if cond1.attribute != cond2.attribute:
            return None
        
        # Try to merge the differing condition
        merged_condition = _merge_conditions(cond1, cond2)
        
        if merged_condition is None:
            return None
        
        # Build merged rule
        new_conditions = []
        for idx, cond in enumerate(conds1):
            if idx == diff_idx:
                new_conditions.append(merged_condition)
            else:
                new_conditions.append(cond)
        
        # Create merged rule
        merged_rule = ABACRule(
            rule_id=new_rule_id,
            effect="permit",
            action=rule1.action,
            conditions=new_conditions,
            support=0.0,  # Will be computed later if needed
            confidence=0.0,  # Computed below
            n_covered_positive=0,
            n_covered_negative=0,
            status="optimised",
            source="merged",
            derived_from=[rule1.rule_id, rule2.rule_id]
        )
        
        # Validate confidence threshold
        merged_confidence = confidence(merged_rule, samples)
        merged_rule.confidence = merged_confidence
        
        min_threshold = cfg.min_confidence - cfg.confidence_tolerance
        
        if merged_confidence < min_threshold:
            return None
        
        return merged_rule
        
    except Exception:
        # Fail-safe: refuse merge on any error
        return None


def _merge_conditions(cond1: Condition, cond2: Condition) -> Condition | None:
    """Merge two conditions on the same attribute.
    
    Merging strategies:
    - Both == operators: merge values into 'in' set
    - Both comparison operators: widen to looser bound
    - One 'in' and one ==: add to 'in' set
    
    Args:
        cond1: First condition
        cond2: Second condition
        
    Returns:
        Merged condition if possible, None otherwise
    """
    try:
        # Both must have same attribute
        if cond1.attribute != cond2.attribute:
            return None
        
        # Strategy 1: Both use == operator -> merge into 'in' set
        if cond1.operator == Operator.EQ and cond2.operator == Operator.EQ:
            values = [cond1.value, cond2.value]
            return Condition(
                attribute=cond1.attribute,
                operator=Operator.IN,
                value=values
            )
        
        # Strategy 2: One 'in' and one == -> add to 'in' set
        if cond1.operator == Operator.IN and cond2.operator == Operator.EQ:
            if isinstance(cond1.value, list):
                values = cond1.value + [cond2.value]
                return Condition(
                    attribute=cond1.attribute,
                    operator=Operator.IN,
                    value=values
                )
        
        if cond1.operator == Operator.EQ and cond2.operator == Operator.IN:
            if isinstance(cond2.value, list):
                values = [cond1.value] + cond2.value
                return Condition(
                    attribute=cond1.attribute,
                    operator=Operator.IN,
                    value=values
                )
        
        # Strategy 3: Both 'in' operators -> merge sets
        if cond1.operator == Operator.IN and cond2.operator == Operator.IN:
            if isinstance(cond1.value, list) and isinstance(cond2.value, list):
                values = cond1.value + cond2.value
                return Condition(
                    attribute=cond1.attribute,
                    operator=Operator.IN,
                    value=values
                )
        
        # Strategy 4: Numeric comparisons -> widen bounds
        # >= with >= -> keep the smaller (looser) bound
        if cond1.operator == Operator.GTE and cond2.operator == Operator.GTE:
            looser_value = min(cond1.value, cond2.value)
            return Condition(
                attribute=cond1.attribute,
                operator=Operator.GTE,
                value=looser_value
            )
        
        # <= with <= -> keep the larger (looser) bound
        if cond1.operator == Operator.LTE and cond2.operator == Operator.LTE:
            looser_value = max(cond1.value, cond2.value)
            return Condition(
                attribute=cond1.attribute,
                operator=Operator.LTE,
                value=looser_value
            )
        
        # > with > -> keep the smaller (looser) bound
        if cond1.operator == Operator.GT and cond2.operator == Operator.GT:
            looser_value = min(cond1.value, cond2.value)
            return Condition(
                attribute=cond1.attribute,
                operator=Operator.GT,
                value=looser_value
            )
        
        # < with < -> keep the larger (looser) bound
        if cond1.operator == Operator.LT and cond2.operator == Operator.LT:
            looser_value = max(cond1.value, cond2.value)
            return Condition(
                attribute=cond1.attribute,
                operator=Operator.LT,
                value=looser_value
            )
        
        # Different operators or incompatible types -> cannot merge
        return None
        
    except Exception:
        # Fail-safe: refuse merge on any error
        return None
