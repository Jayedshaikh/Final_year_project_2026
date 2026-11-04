"""
Policy Engine Module - ABAC Rule Optimization, Validation, and Export

Owner: Granthali Sandesh Mahajan
Module: policy_engine/

Public API for ABAC policy optimization, validation against full RBAC access matrix,
and export to JSON/XACML formats.

Dependencies:
    - shared/schemas/contracts.py (frozen contracts)
    - pandas, numpy, pydantic>=2

Constraints:
    - NO imports from backend/ (circular dependency forbidden)
    - NO scikit-learn, NO FastAPI
    - NO ML model training
    - NO auto-approval of rules
    - Fail-safe: errors -> deny (never allow)
    - Default decision: deny (closed world)
"""

import pandas as pd
from shared.schemas.contracts import (
    ABACRule,
    PolicyMetrics,
    AuthorisationTuple,
    OptimisationSummary,
)

# Import submodules
from policy_engine.schemas.config import OptimisationConfig
from policy_engine.schemas.rbac import verify_rbac_authorisation
from policy_engine.rule_merger.merger import merge_rules
from policy_engine.rule_generalizer.generalizer import generalise_rules
from policy_engine.rule_pruner.pruner import prune_rules
from policy_engine.policy_validator.validator import validate_policy
from policy_engine.policy_exporter.exporter import export_policy


def optimise_policy(
    rules: list[ABACRule], samples_df: pd.DataFrame, config: OptimisationConfig
) -> tuple[list[ABACRule], OptimisationSummary]:
    """
    Optimize ABAC policy through filtering, merging, generalization, and pruning.

    Pipeline Order: Filter → Merge → Generalize → Prune

    Args:
        rules: List of candidate ABAC rules to optimize
        samples_df: Sample data with columns:
            user_id, resource_id, permission, user.<attrs>, resource.<attrs>, authorised
        config: Optimization configuration (thresholds, weights, seed)

    Returns:
        Tuple of:
        - optimized_rules: List of optimized ABACRule objects
        - summary: OptimisationSummary with counts and before/after metrics

    Steps:
        1. Filter: Remove rules below min_support or min_confidence
        2. Merge: Combine rules differing in one condition (evidence-based)
        3. Generalize: Remove conditions safely (confidence-preserving)
        4. Prune: Remove redundant and low-support rules (idempotent)

    Each step validates against evidence and never introduces over-privilege
    beyond configured tolerance.
    """
    from policy_engine.policy_validator.wsc import weighted_structural_complexity

    # Initial metrics
    rules_before = len(rules)
    wsc_before = weighted_structural_complexity(rules, config.wsc_weights)

    # Step 1: Filter low-support/confidence rules
    filtered_rules = []
    n_filtered = 0
    for rule in rules:
        if rule.support is not None and rule.support < config.min_support:
            n_filtered += 1
            continue
        if rule.confidence is not None and rule.confidence < config.min_confidence:
            n_filtered += 1
            continue
        filtered_rules.append(rule)

    # Step 2: Merge rules
    merged_rules, n_merged = merge_rules(filtered_rules, samples_df, config)

    # Step 3: Generalize rules
    generalised_rules, n_generalised = generalise_rules(merged_rules, samples_df, config)

    # Step 4: Prune redundant rules
    pruned_rules, n_pruned_redundant = prune_rules(generalised_rules, samples_df, config)

    # Final metrics
    rules_after = len(pruned_rules)
    wsc_after = weighted_structural_complexity(pruned_rules, config.wsc_weights)

    # Build summary
    summary = OptimisationSummary(
        n_merged=n_merged,
        n_generalised=n_generalised,
        n_pruned_redundant=n_pruned_redundant,
        rules_before=rules_before,
        rules_after=rules_after,
        wsc_before=wsc_before,
        wsc_after=wsc_after,
    )

    return pruned_rules, summary


# Re-export public API
__all__ = [
    "optimise_policy",
    "validate_policy",
    "export_policy",
    "verify_rbac_authorisation",
    "OptimisationConfig",
]
