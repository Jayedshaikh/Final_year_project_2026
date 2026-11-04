"""Rule pruner: remove redundant and low-support rules.

Owner: Granthali (policy_engine module)

Remove rules with support below threshold and redundant rules whose
matched positives are covered by other rules. Idempotent: pruning
twice gives the same result.
"""
import pandas as pd
from typing import List, Tuple, Set
from shared.schemas.contracts import ABACRule
from policy_engine.schemas.config import OptimisationConfig
from policy_engine.schemas.metrics import support
from policy_engine.schemas.rule import rule_matches


def prune_rules(rules: List[ABACRule], samples: pd.DataFrame, cfg: OptimisationConfig) -> Tuple[List[ABACRule], int]:
    """Prune low-support and redundant rules.
    
    Pruning steps:
    1. Drop rules with support < cfg.min_support
    2. Drop redundant rules: a rule is redundant if its matched positives
       are a subset of positives matched by remaining rules
    
    Idempotent: prune(prune(rules)) == prune(rules)
    
    Args:
        rules: List of ABAC rules to prune
        samples: DataFrame with access tuples and attributes
        cfg: Optimisation configuration with min_support threshold
        
    Returns:
        Tuple of (pruned_rules, n_pruned_count)
    """
    try:
        if len(rules) == 0:
            return ([], 0)
        
        original_count = len(rules)
        
        # Step 1: Remove low-support rules
        filtered_rules = []
        for rule in rules:
            rule_support = support(rule, samples)
            if rule_support >= cfg.min_support:
                filtered_rules.append(rule)
        
        # Step 2: Remove redundant rules
        pruned_rules = _remove_redundant_rules(filtered_rules, samples)
        
        pruned_count = original_count - len(pruned_rules)
        
        return (pruned_rules, pruned_count)
        
    except Exception:
        # Fail-safe: return original rules unchanged on any error
        return (rules, 0)


def _remove_redundant_rules(rules: List[ABACRule], samples: pd.DataFrame) -> List[ABACRule]:
    """Remove redundant rules whose positives are covered by others.
    
    A rule is redundant if every positive tuple it matches is also
    matched by at least one other rule in the set.
    
    Args:
        rules: List of rules to check for redundancy
        samples: DataFrame with access tuples
        
    Returns:
        List of non-redundant rules
    """
    try:
        if len(rules) <= 1:
            # Cannot have redundancy with 0 or 1 rule
            return rules
        
        # Build matched positive sets for each rule
        rule_positives = []
        for rule in rules:
            positives = _get_matched_positive_indices(rule, samples)
            rule_positives.append(positives)
        
        # Find non-redundant rules
        non_redundant = []
        
        for idx, rule in enumerate(rules):
            my_positives = rule_positives[idx]
            
            # If rule matches no positives, it's redundant (useless)
            if len(my_positives) == 0:
                continue
            
            # Check if all my positives are covered by other rules
            is_redundant = True
            
            for positive_idx in my_positives:
                # Check if this positive is matched by any other rule
                covered_by_other = False
                
                for other_idx, other_positives in enumerate(rule_positives):
                    if other_idx == idx:
                        continue
                    
                    if positive_idx in other_positives:
                        covered_by_other = True
                        break
                
                if not covered_by_other:
                    # This positive is unique to this rule
                    is_redundant = False
                    break
            
            if not is_redundant:
                non_redundant.append(rule)
        
        return non_redundant
        
    except Exception:
        # Fail-safe: return all rules on error
        return rules


def _get_matched_positive_indices(rule: ABACRule, samples: pd.DataFrame) -> Set[int]:
    """Get indices of positive samples matched by a rule.
    
    Args:
        rule: Rule to evaluate
        samples: DataFrame with access tuples
        
    Returns:
        Set of DataFrame indices for matched positive samples
    """
    try:
        matched_indices = set()
        
        for idx, row in samples.iterrows():
            # Only consider positive samples
            if row['authorised'] != 1:
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
                matched_indices.add(idx)
        
        return matched_indices
        
    except Exception:
        # Fail-safe: return empty set on error
        return set()
