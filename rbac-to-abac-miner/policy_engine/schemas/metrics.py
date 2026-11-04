"""Support and confidence metrics for ABAC rules.

Owner: Granthali (policy_engine module)

Per POLICY_ENGINE.md section 3, support and confidence on sampled data are estimates;
final metrics are recomputed on the full access matrix.
"""
import pandas as pd
from shared.schemas.contracts import ABACRule
from .rule import rule_matches


def support(rule: ABACRule, samples: pd.DataFrame) -> float:
    """Compute support metric for a rule.
    
    Support = number of samples matched by rule / total number of samples
    
    Expected samples columns:
    - user_id, resource_id, permission: identifiers
    - user.*: user attributes
    - resource.*: resource attributes
    - authorised: 0/1 flag
    
    Args:
        rule: ABAC rule to evaluate
        samples: DataFrame with access tuples and attributes
        
    Returns:
        Support value in [0, 1]. Returns 0.0 if samples is empty (avoid division by zero)
    """
    if len(samples) == 0:
        return 0.0
    
    matched_count = 0
    
    for _, row in samples.iterrows():
        # Extract user attributes (columns starting with 'user.')
        user_attrs = {}
        for col in samples.columns:
            if col.startswith('user.'):
                attr_name = col[5:]  # Remove 'user.' prefix
                user_attrs[attr_name] = row[col]
        
        # Extract resource attributes (columns starting with 'resource.')
        resource_attrs = {}
        for col in samples.columns:
            if col.startswith('resource.'):
                attr_name = col[9:]  # Remove 'resource.' prefix
                resource_attrs[attr_name] = row[col]
        
        # Check if rule matches this sample
        if rule_matches(rule, user_attrs, resource_attrs, row['permission']):
            matched_count += 1
    
    return matched_count / len(samples)


def confidence(rule: ABACRule, samples: pd.DataFrame) -> float:
    """Compute confidence metric for a rule.
    
    Confidence = number of matched positive samples / number of matched samples
    
    A positive sample is one where authorised == 1.
    
    Expected samples columns:
    - user_id, resource_id, permission: identifiers
    - user.*: user attributes
    - resource.*: resource attributes
    - authorised: 0/1 flag
    
    Args:
        rule: ABAC rule to evaluate
        samples: DataFrame with access tuples and attributes
        
    Returns:
        Confidence value in [0, 1]. Returns 0.0 if no samples are matched (avoid division by zero)
    """
    if len(samples) == 0:
        return 0.0
    
    matched_rows = []
    
    for idx, row in samples.iterrows():
        # Extract user attributes (columns starting with 'user.')
        user_attrs = {}
        for col in samples.columns:
            if col.startswith('user.'):
                attr_name = col[5:]  # Remove 'user.' prefix
                user_attrs[attr_name] = row[col]
        
        # Extract resource attributes (columns starting with 'resource.')
        resource_attrs = {}
        for col in samples.columns:
            if col.startswith('resource.'):
                attr_name = col[9:]  # Remove 'resource.' prefix
                resource_attrs[attr_name] = row[col]
        
        # Check if rule matches this sample
        if rule_matches(rule, user_attrs, resource_attrs, row['permission']):
            matched_rows.append(row)
    
    if len(matched_rows) == 0:
        return 0.0
    
    # Count positives (authorised == 1) among matched rows
    positive_count = sum(1 for row in matched_rows if row['authorised'] == 1)
    
    return positive_count / len(matched_rows)
