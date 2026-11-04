"""
Policy validation against full RBAC access matrix.

PERFORMANCE: Uses vectorised pandas operations instead of iterrows()
so it handles 150k+ tuples in seconds instead of minutes.
"""
from __future__ import annotations

import pandas as pd
from shared.schemas.contracts import ABACRule, PolicyMetrics, AuthorisationTuple
from policy_engine.policy_validator.wsc import weighted_structural_complexity


def validate_policy(
    rules: list[ABACRule],
    access_matrix_df: pd.DataFrame,
    user_attrs_df: pd.DataFrame,
    resource_attrs_df: pd.DataFrame,
    wsc_weights: dict[str, float] | None = None,
) -> tuple[PolicyMetrics, list[AuthorisationTuple], list[AuthorisationTuple]]:
    """
    Validate ABAC policy against the full RBAC access matrix.

    Vectorised implementation: joins attributes once, evaluates each rule as
    a boolean column, ORs them together. O(n_tuples * n_rules) but no Python
    loop over rows — handles 200k+ tuples in under a second.

    Args:
        rules: ABAC rules (rejected rules are excluded per D-010).
        access_matrix_df: Full matrix — user_id, resource_id, permission, authorised.
        user_attrs_df: user_id + attribute columns.
        resource_attrs_df: resource_id + attribute columns.
        wsc_weights: Optional WSC weight overrides.

    Returns:
        (PolicyMetrics, over_privileged_examples, under_privileged_examples)
    """
    # ── 1. Filter active rules (exclude rejected) ─────────────────────────
    counted_statuses = {"candidate", "optimised", "approved", "edited"}
    active_rules = [r for r in rules if r.status in counted_statuses]

    # ── 2. Build a wide DataFrame: matrix + user attrs + resource attrs ───
    # Normalise all string attribute values to lowercase once.
    def _normalise(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in df.columns:
            # Handle both object dtype (Pandas 2) and StringDtype (Pandas 3)
            if (df[col].dtype == object
                    or str(df[col].dtype) == "string"
                    or df[col].dtype.name == "string"
                    or pd.api.types.is_string_dtype(df[col])):
                try:
                    df[col] = df[col].str.lower()
                except AttributeError:
                    pass
        return df

    users_norm = _normalise(user_attrs_df)
    resources_norm = _normalise(resource_attrs_df)

    # Rename attribute columns with prefixes for the join
    u_attr_cols = [c for c in users_norm.columns if c != "user_id"]
    r_attr_cols = [c for c in resources_norm.columns if c != "resource_id"]
    users_renamed     = users_norm.rename(columns={c: f"user.{c}"     for c in u_attr_cols})
    resources_renamed = resources_norm.rename(columns={c: f"resource.{c}" for c in r_attr_cols})

    df = (
        access_matrix_df
        .merge(users_renamed,     on="user_id",     how="left")
        .merge(resources_renamed, on="resource_id",  how="left")
    )
    df["authorised"] = df["authorised"].astype(int)

    # ── 3. Evaluate every rule as a boolean Series ─────────────────────────
    if not active_rules:
        policy_permits = pd.Series(False, index=df.index)
    else:
        any_match = pd.Series(False, index=df.index)
        for rule in active_rules:
            match = _evaluate_rule_vectorised(rule, df)
            any_match = any_match | match
        policy_permits = any_match

    # ── 4. Classify TP / FP / FN / TN ────────────────────────────────────
    rbac_auth     = df["authorised"] == 1
    tp_mask = policy_permits &  rbac_auth
    fp_mask = policy_permits & ~rbac_auth
    fn_mask = ~policy_permits &  rbac_auth
    tn_mask = ~policy_permits & ~rbac_auth

    tp = int(tp_mask.sum())
    fp = int(fp_mask.sum())
    fn = int(fn_mask.sum())
    tn = int(tn_mask.sum())

    # ── 5. Collect examples (capped at 20) ────────────────────────────────
    MAX_EXAMPLES = 20

    def _to_tuples(mask: pd.Series) -> list[AuthorisationTuple]:
        rows = df[mask].head(MAX_EXAMPLES)
        return [
            AuthorisationTuple(
                user_id=str(row["user_id"]),
                resource_id=str(row["resource_id"]),
                permission=str(row["permission"]),
            )
            for _, row in rows.iterrows()
        ]

    over_privileged  = _to_tuples(fp_mask)
    under_privileged = _to_tuples(fn_mask)

    # ── 6. Compute metrics ────────────────────────────────────────────────
    n_tuples           = len(df)
    n_rbac_authorised  = tp + fn
    n_rbac_unauthorised = fp + tn

    precision = tp / (tp + fp)              if (tp + fp) > 0 else 0.0
    recall    = tp / n_rbac_authorised      if n_rbac_authorised > 0 else 1.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    opr       = fp / n_rbac_unauthorised    if n_rbac_unauthorised > 0 else 0.0
    upr       = fn / n_rbac_authorised      if n_rbac_authorised > 0 else 0.0
    wsc       = weighted_structural_complexity(active_rules, wsc_weights)

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


# ── Vectorised rule evaluator ──────────────────────────────────────────────

def _evaluate_rule_vectorised(rule: ABACRule, df: pd.DataFrame) -> pd.Series:
    """Return a boolean Series — True where the rule permits a row.

    Fail-safe: any error for a condition column returns False for the whole rule.
    """
    try:
        # Action must match permission column
        match = df["permission"] == rule.action.lower()

        for cond in rule.conditions:
            attr  = cond.attribute          # e.g. "user.department"
            op    = cond.operator.value if hasattr(cond.operator, "value") else str(cond.operator)
            val   = cond.value

            if attr not in df.columns:
                return pd.Series(False, index=df.index)

            col = df[attr]

            # Normalise condition value(s) to lowercase strings
            if isinstance(val, str):
                val = val.lower()
            elif isinstance(val, list):
                val = [v.lower() if isinstance(v, str) else v for v in val]

            try:
                if op == "==":
                    cond_match = col == val
                elif op == "!=":
                    cond_match = col != val
                elif op == "in":
                    cond_match = col.isin(val if isinstance(val, list) else [val])
                elif op == "not_in":
                    cond_match = ~col.isin(val if isinstance(val, list) else [val])
                elif op == "<=":
                    cond_match = pd.to_numeric(col, errors="coerce") <= float(val)
                elif op == ">":
                    cond_match = pd.to_numeric(col, errors="coerce") > float(val)
                elif op == ">=":
                    cond_match = pd.to_numeric(col, errors="coerce") >= float(val)
                elif op == "<":
                    cond_match = pd.to_numeric(col, errors="coerce") < float(val)
                else:
                    return pd.Series(False, index=df.index)
            except Exception:
                return pd.Series(False, index=df.index)

            match = match & cond_match.fillna(False)

        return match.fillna(False)

    except Exception:
        # Fail-safe: any error → deny
        return pd.Series(False, index=df.index)
