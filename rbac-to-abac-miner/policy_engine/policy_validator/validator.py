"""
Policy validation against full RBAC access matrix.

Evaluates every tuple in the complete access matrix (never only sampled negatives)
and computes precision, recall, F1, OPR, UPR, and WSC metrics.
"""

import pandas as pd
from shared.schemas.contracts import ABACRule, PolicyMetrics, AuthorisationTuple
from policy_engine.schemas.rule import rule_matches
from policy_engine.policy_validator.wsc import weighted_structural_complexity


def validate_policy(
    rules: list[ABACRule],
    access_matrix_df: pd.DataFrame,
    user_attrs_df: pd.DataFrame,
    resource_attrs_df: pd.DataFrame,
    wsc_weights: dict[str, float] | None = None,
) -> tuple[PolicyMetrics, list[AuthorisationTuple], list[AuthorisationTuple]]:
    """
    Validate ABAC policy against full RBAC access matrix.

    Args:
        rules: List of ABAC rules to evaluate (statuses: candidate, optimised, approved, edited)
               Rejected rules are excluded per decision D-010
        access_matrix_df: Full access matrix with columns:
            user_id, resource_id, permission, authorised (0/1)
        user_attrs_df: User attributes (user_id + attribute columns)
        resource_attrs_df: Resource attributes (resource_id + attribute columns)
        wsc_weights: Optional custom WSC weights

    Returns:
        Tuple of:
        - PolicyMetrics: Precision, recall, F1, OPR, UPR, rule_count, WSC
        - over_privileged_examples: List of FP tuples (permitted by policy, not by RBAC)
        - under_privileged_examples: List of FN tuples (permitted by RBAC, not by policy)

    Metrics Definitions (per VALIDATION.md and POLICY_ENGINE.md):
        - TP (True Positive): Permitted by both policy and RBAC
        - FP (False Positive): Permitted by policy, NOT by RBAC (over-privileged)
        - FN (False Negative): Permitted by RBAC, NOT by policy (under-privileged)
        - TN (True Negative): Denied by both
        - Precision = TP / (TP + FP), handle TP+FP=0 -> 0.0
        - Recall = TP / (TP + FN), handle TP+FN=0 -> 1.0 (no positives to miss)
        - F1 = 2 * precision * recall / (precision + recall), handle sum=0 -> 0.0
        - OPR = FP / (FP + TN) = FP / n_rbac_unauthorised, handle denom=0 -> 0.0
        - UPR = FN / (FN + TP) = FN / n_rbac_authorised, handle denom=0 -> 0.0

    Evaluation Rules:
        - Default decision: DENY (closed world)
        - Tuple permitted if ANY rule matches (permit-overrides semantics)
        - Counted rules: status in {candidate, optimised, approved, edited}
        - Rejected rules excluded per D-010
        - Fail-safe: Any error during evaluation -> deny
    """
    # Filter rules by status (exclude rejected)
    counted_statuses = {"candidate", "optimised", "approved", "edited"}
    active_rules = [r for r in rules if r.status in counted_statuses]

    # Build attribute lookup dicts — normalise categorical values to lowercase
    # to match rule condition values (which are lowercased during training/extraction)
    def _normalise_attrs(df: pd.DataFrame, id_col: str) -> dict:
        """Build attribute lookup dict with lowercased string values."""
        result = {}
        for _, row in df.iterrows():
            key = row[id_col]
            attrs = {}
            for col in df.columns:
                if col == id_col:
                    continue
                val = row[col]
                # Lowercase strings; leave numbers as-is
                if isinstance(val, str):
                    attrs[col] = val.lower()
                else:
                    attrs[col] = val
            result[key] = attrs
        return result

    user_attrs_dict = _normalise_attrs(user_attrs_df, "user_id")
    resource_attrs_dict = _normalise_attrs(resource_attrs_df, "resource_id")

    # Initialize counters
    tp = fp = fn = tn = 0
    over_privileged = []
    under_privileged = []

    # Evaluate every tuple in access matrix
    for _, row in access_matrix_df.iterrows():
        user_id = row["user_id"]
        resource_id = row["resource_id"]
        permission = row["permission"]
        rbac_authorised = bool(row["authorised"])

        # Get attributes (handle missing gracefully)
        user_attrs = user_attrs_dict.get(user_id, {})
        resource_attrs = resource_attrs_dict.get(resource_id, {})

        # Evaluate policy: tuple permitted if ANY rule matches
        policy_permits = False
        try:
            for rule in active_rules:
                if rule_matches(rule, user_attrs, resource_attrs, permission):
                    policy_permits = True
                    break
        except Exception:
            # Fail-safe: exception during evaluation -> deny
            policy_permits = False

        # Classify outcome
        if policy_permits and rbac_authorised:
            tp += 1
        elif policy_permits and not rbac_authorised:
            fp += 1
            over_privileged.append(
                AuthorisationTuple(
                    user_id=user_id,
                    resource_id=resource_id,
                    permission=permission,
                )
            )
        elif not policy_permits and rbac_authorised:
            fn += 1
            under_privileged.append(
                AuthorisationTuple(
                    user_id=user_id,
                    resource_id=resource_id,
                    permission=permission,
                )
            )
        else:  # not policy_permits and not rbac_authorised
            tn += 1

    # Compute metrics with zero-denominator handling
    n_tuples = len(access_matrix_df)
    n_rbac_authorised = tp + fn
    n_rbac_unauthorised = fp + tn

    # Precision: TP / (TP + FP)
    if (tp + fp) == 0:
        precision = 0.0
    else:
        precision = tp / (tp + fp)

    # Recall: TP / (TP + FN)
    if n_rbac_authorised == 0:
        recall = 1.0  # No positives to miss
    else:
        recall = tp / n_rbac_authorised

    # F1: harmonic mean
    if (precision + recall) == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    # OPR: FP / n_rbac_unauthorised
    if n_rbac_unauthorised == 0:
        opr = 0.0
    else:
        opr = fp / n_rbac_unauthorised

    # UPR: FN / n_rbac_authorised
    if n_rbac_authorised == 0:
        upr = 0.0
    else:
        upr = fn / n_rbac_authorised

    # WSC
    wsc = weighted_structural_complexity(active_rules, wsc_weights)

    # Build PolicyMetrics
    metrics = PolicyMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        over_privilege_rate=opr,
        under_privilege_rate=upr,
        rule_count=len(active_rules),
        wsc=wsc,
        evaluated_on="full_access_matrix",
        n_tuples_evaluated=n_tuples,
    )

    return metrics, over_privileged, under_privileged
