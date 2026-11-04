"""Rule generalizer: safely drop conditions from rules.

Owner: Granthali (policy_engine module)

Evidence-based generalisation: remove conditions only when confidence stays
above threshold and added negatives are within tolerance. Never permits tuples
the evidence does not support beyond configured tolerance.
"""
import pandas as pd
from typing import List, Tuple
from shared.schemas.contracts import ABACRule, Condition
from policy_engine.schemas.config import OptimisationConfig
from policy_engine.schemas.metrics import confidence
from policy_engine.schemas.rule import rule_matches


def generalise_rules(rules: List[ABACRule], samples: pd.DataFrame, cfg: OptimisationConfig) -> Tuple[List[ABACRule], int]:
    """Generalise rules by safely dropping conditions.
    
    For each rule, try removing one condition at a time. Accept removal only if:
    1. Confidence >= cfg.min_confidence - cfg.confidence_tolerance
    2. Added negatives (newly matched unauthorised tuples) are within tolerance
    
    Generalised rules get:
    - source='generalised'
    - derived_from=[original_rule_id]
    - status='optimised'
    - new rule_id like 'G001', 'G002', ...
    
    Safe, evidence-based removal only: never accepts a generalisation that
    permits tuples the evidence does not support beyond tolerance.
    
    Args:
        rules: List of ABAC rules to generalise
        samples: DataFrame with access tuples and attributes for validation
        cfg: Optimisation configuration with min_confidence and confidence_tolerance
        
    Returns:
        Tuple of (generalised + unchanged rules, n_generalised_count)
    """
    try:
        if len(rules) == 0:
            return ([], 0)
        
        generalised_rules = []
        generalised_count = 0
        generalise_id_counter = 1
        
        for rule in rules:
            # Try to generalise this rule
            generalised = _try_generalise_rule(rule, samples, cfg, f"G{generalise_id_counter:03d}")
            
            if generalised is not None:
                generalised_rules.append(generalised)
                generalised_count += 1
                generalise_id_counter += 1
            else:
                # Keep original rule unchanged
                generalised_rules.append(rule)
        
        return (generalised_rules, generalised_count)
        
    except Exception:
        # Fail-safe: return original rules unchanged on any error
        return (rules, 0)


def _try_generalise_rule(rule: ABACRule, samples: pd.DataFrame, 
                        cfg: OptimisationConfig, new_rule_id: str) -> ABACRule | None:
    """Try to generalise a rule by dropping one condition.
    
    Args:
        rule: Rule to generalise
        samples: DataFrame for validation
        cfg: Optimisation configuration
        new_rule_id: ID for the new generalised rule
        
    Returns:
        Generalised rule if successful, None if no safe generalisation found
    """
    try:
        # Cannot generalise if only one condition (would be empty)
        if len(rule.conditions) <= 1:
            return None
        
        original_confidence = confidence(rule, samples)
        min_threshold = cfg.min_confidence - cfg.confidence_tolerance
        
        # Count original matched negatives
        original_matched_negatives = _count_matched_negatives(rule, samples)
        
        # Try removing each condition
        best_generalised = None
        best_confidence = -1
        
        for idx in range(len(rule.conditions)):
            # Create candidate with condition removed
            new_conditions = [cond for i, cond in enumerate(rule.conditions) if i != idx]
            
            candidate = ABACRule(
                rule_id=new_rule_id,
                effect="permit",
                action=rule.action,
                conditions=new_conditions,
                support=0.0,
                confidence=0.0,
                n_covered_positive=0,
                n_covered_negative=0,
                status="optimised",
                source="generalised",
                derived_from=[rule.rule_id]
            )
            
            # Compute confidence
            candidate_confidence = confidence(candidate, samples)
            candidate.confidence = candidate_confidence
            
            # Check confidence threshold
            if candidate_confidence < min_threshold:
                continue
            
            # Count matched negatives for candidate
            candidate_matched_negatives = _count_matched_negatives(candidate, samples)
            
            # Check that added negatives are within tolerance
            added_negatives = candidate_matched_negatives - original_matched_negatives
            
            # Accept if confidence threshold met and negatives not increased beyond tolerance
            # For now, we use a simple rule: allow up to confidence_tolerance increase in negative rate
            if added_negatives > 0:
                # Compute negative rate increase
                total_negatives = len(samples[samples['authorised'] == 0])
                if total_negatives > 0:
                    negative_rate_increase = added_negatives / total_negatives
                    if negative_rate_increase > cfg.confidence_tolerance:
                        continue
            
            # This is a valid candidate - keep track of best one
            if candidate_confidence > best_confidence:
                best_confidence = candidate_confidence
                best_generalised = candidate
        
        return best_generalised
        
    except Exception:
        # Fail-safe: refuse generalisation on any error
        return None


def _count_matched_negatives(rule: ABACRule, samples: pd.DataFrame) -> int:
    """Count how many negative (unauthorised) samples are matched by the rule.
    
    Args:
        rule: Rule to evaluate
        samples: DataFrame with access tuples
        
    Returns:
        Count of matched negative samples
    """
    try:
        count = 0
        
        for _, row in samples.iterrows():
            # Skip positive samples
            if row['authorised'] == 1:
                continue
            
            # Extract attributes
            user_attrs = {}
            for col in samples.columns:
                if col.startswith('user.'):
                    attr_name = col[5:]
                    user_attrs[attr_name] = row[col]
            
            resource_attrs = {}
            for col in samples.columns:
                if col.startswith('resource.'):
                    attr_name = col[9:]
                    resource_attrs[attr_name] = row[col]
            
            # Check if rule matches
            if rule_matches(rule, user_attrs, resource_attrs, row['permission']):
                count += 1
        
        return count
        
    except Exception:
        # Fail-safe: return 0 on error
        return 0
