"""Decision Tree rule extraction.

Walks the fitted Decision Tree and extracts every root-to-leaf path that
predicts "permit" (positive class, label == 1) as an ABACRule.

Algorithm step 13-15 from project specification Appendix B.

Note: Rule extraction is ONLY performed on the Decision Tree.
      Never extract from Random Forest or Gradient Boosting.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from backend.data_pipeline.preprocess import FeatureEncoder
from shared.schemas.contracts import ABACRule, Condition, Operator, RuleStatus

logger = logging.getLogger(__name__)

# TEMPORARY: support/confidence helper until policy_engine functions are available.
# Replace with policy_engine.compute_support_confidence once Granthali's module is ready.


def _compute_support_confidence(  # TEMPORARY
    conditions: List[Condition],
    action: str,
    samples: pd.DataFrame,
) -> Tuple[float, float, int, int]:
    """Compute support and confidence for a rule on samples. TEMPORARY implementation.

    Definitions (DATA_CONTRACTS.md / POLICY_ENGINE.md section 3):
        matched = rows in samples where rule matches (action matches AND all conditions hold)
        support = |matched| / |samples|
        confidence = |matched with authorised == 1| / |matched|
                     (0.0 when |matched| == 0)

    Args:
        conditions: List of rule conditions.
        action: Rule action/permission (e.g. "read").
        samples: DataFrame with decoded feature columns and "authorised" label.
                 Must include a "permission" column.

    Returns:
        Tuple (support, confidence, n_covered_positive, n_covered_negative).
    """
    if samples.empty:
        return 0.0, 0.0, 0, 0

    n_total = len(samples)
    mask = samples["permission"] == action if "permission" in samples.columns else pd.Series([True] * n_total, index=samples.index)

    for cond in conditions:
        attr = cond.attribute  # e.g. "user.department"
        if attr not in samples.columns:
            # condition attribute not in samples -> no rows match
            mask = mask & pd.Series([False] * n_total, index=samples.index)
            continue
        col = samples[attr]
        val = cond.value
        op = cond.operator

        try:
            if op == Operator.EQ:
                mask = mask & (col == val)
            elif op == Operator.NEQ:
                mask = mask & (col != val)
            elif op == Operator.IN:
                mask = mask & col.isin(val if isinstance(val, list) else [val])
            elif op == Operator.NOT_IN:
                mask = mask & ~col.isin(val if isinstance(val, list) else [val])
            elif op == Operator.LTE:
                mask = mask & (pd.to_numeric(col, errors="coerce") <= float(val))
            elif op == Operator.GT:
                mask = mask & (pd.to_numeric(col, errors="coerce") > float(val))
            elif op == Operator.GTE:
                mask = mask & (pd.to_numeric(col, errors="coerce") >= float(val))
            elif op == Operator.LT:
                mask = mask & (pd.to_numeric(col, errors="coerce") < float(val))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Condition evaluation failed for %s %s %s: %s", attr, op, val, exc)
            mask = mask & pd.Series([False] * n_total, index=samples.index)

    matched = samples[mask]
    n_matched = len(matched)
    n_pos = int(matched["authorised"].sum()) if "authorised" in matched.columns else 0
    n_neg = n_matched - n_pos

    support = n_matched / n_total if n_total > 0 else 0.0
    confidence = n_pos / n_matched if n_matched > 0 else 0.0

    return support, confidence, n_pos, n_neg


def _apply_conditions_to_df(conditions: List[Condition], df: pd.DataFrame) -> pd.DataFrame:
    """Filter a DataFrame to rows satisfying all given conditions.

    Used internally to find covered samples when permission is not a split feature.
    Silently skips conditions whose attribute is absent or causes a type error (fail-safe).

    Args:
        conditions: List of Condition objects to apply.
        df: Input DataFrame with decoded attribute columns.

    Returns:
        Filtered DataFrame (subset of df).
    """
    result = df.copy()
    for cond in conditions:
        attr = cond.attribute
        if attr not in result.columns:
            continue
        col = result[attr]
        val = cond.value
        op = cond.operator
        try:
            if op == Operator.EQ:
                result = result[col.astype(str) == str(val)]
            elif op == Operator.NEQ:
                result = result[col.astype(str) != str(val)]
            elif op == Operator.IN:
                result = result[col.astype(str).isin([str(v) for v in val])]
            elif op == Operator.NOT_IN:
                result = result[~col.astype(str).isin([str(v) for v in val])]
            elif op in (Operator.LTE, Operator.GT, Operator.GTE, Operator.LT):
                num_col = pd.to_numeric(col, errors="coerce")
                fv = float(val)
                if op == Operator.LTE:
                    result = result[num_col <= fv]
                elif op == Operator.GT:
                    result = result[num_col > fv]
                elif op == Operator.GTE:
                    result = result[num_col >= fv]
                elif op == Operator.LT:
                    result = result[num_col < fv]
        except Exception:  # noqa: BLE001
            pass  # fail-safe: skip condition if it errors
    return result


def extract_permit_rules(
    tree: DecisionTreeClassifier,
    feature_names: List[str],
    encoder: FeatureEncoder,
    samples: pd.DataFrame,
    min_support: float = 0.01,
    min_confidence: float = 0.9,
) -> List[ABACRule]:
    """Extract permit-path rules from a fitted DecisionTreeClassifier.

    Walk every root-to-leaf path that predicts the positive class (label == 1).
    Decode split thresholds using the FeatureEncoder back to readable conditions
    with user./ resource. prefixes.

    Algorithm details:
      - One-hot feature f=cat with threshold 0.5: '>0.5' -> attr==cat, '<=0.5' -> attr!=cat
      - Numeric feature: <=t or >t preserved as-is
      - The 'permission' feature becomes the rule's action
      - Multiple == conditions on one attribute collapse to 'in'
      - rule_id is R001, R002, ... in depth-first order
      - Filters applied: min_support, min_confidence

    Args:
        tree: Fitted DecisionTreeClassifier (must have tree_ attribute).
        feature_names: Ordered list of feature names (from encoder.feature_names).
        encoder: Fitted FeatureEncoder (used to decode OHE columns).
        samples: DataFrame with decoded columns and 'authorised' label (for support/confidence).
        min_support: Minimum support threshold. Default 0.01.
        min_confidence: Minimum confidence threshold. Default 0.9.

    Returns:
        List of ABACRule objects (status=candidate, source=tree_path).

    Raises:
        ValueError: If the tree is not fitted or feature_names length mismatches.
    """
    tree_ = tree.tree_
    n_features = tree_.n_features
    if len(feature_names) != n_features:
        raise ValueError(
            f"feature_names length {len(feature_names)} != tree n_features {n_features}"
        )

    rules: List[ABACRule] = []
    rule_counter = 0

    # Build a decoded-column samples DataFrame for support/confidence computation
    # (samples already decoded if it came from build_training_samples)

    def _walk(node_id: int, path_conditions: List[Dict]) -> None:
        """Recursively walk tree nodes depth-first.

        Args:
            node_id: Current node index.
            path_conditions: List of raw condition dicts accumulated on the path.
        """
        nonlocal rule_counter

        left_child = tree_.children_left[node_id]
        right_child = tree_.children_right[node_id]

        is_leaf = (left_child == -1) and (right_child == -1)

        if is_leaf:
            # Check if this leaf predicts the positive class
            leaf_values = tree_.value[node_id][0]
            predicted_class = int(np.argmax(leaf_values))
            if predicted_class != 1:
                return  # deny leaf -> skip

            # Group conditions by (scope, attribute) to simplify
            per_attr: Dict[Tuple[str, str], Dict] = defaultdict(lambda: {"eq": set(), "neq": set(), "ranges": []})

            # Collect the permission (action)
            action: Optional[str] = None
            simplified_conditions: List[Condition] = []

            for raw in path_conditions:
                feat_idx: int = raw["feature"]
                direction: str = raw["direction"]  # "left" or "right"
                threshold: float = raw["threshold"]

                scope, attr, category = encoder.feature_map.get(feat_idx, ("", feature_names[feat_idx], None))

                full_attr = f"{scope}.{attr}" if scope else attr

                if category is not None:
                    # One-hot feature: threshold is ~0.5
                    # right (> threshold) -> attr == category
                    # left (<= threshold) -> attr != category
                    if direction == "right":
                        per_attr[(scope, attr)]["eq"].add(category)
                    else:
                        per_attr[(scope, attr)]["neq"].add(category)
                else:
                    # Numeric or permission feature
                    if attr == "permission" and scope == "":
                        if direction == "right":
                            # > threshold is not meaningful for a label-encoded permission
                            pass
                        # We'll handle permission separately
                    else:
                        op = Operator.LTE if direction == "left" else Operator.GT
                        per_attr[(scope, attr)]["ranges"].append((op, float(threshold)))

            # Build conditions
            for (scope, attr), info in per_attr.items():
                full_attr = f"{scope}.{attr}" if scope else attr

                if info["eq"]:
                    vals = sorted(info["eq"])
                    if len(vals) == 1:
                        simplified_conditions.append(
                            Condition(attribute=full_attr, operator=Operator.EQ, value=vals[0])
                        )
                    else:
                        simplified_conditions.append(
                            Condition(attribute=full_attr, operator=Operator.IN, value=vals)
                        )
                elif info["neq"]:
                    vals = sorted(info["neq"])
                    simplified_conditions.append(
                        Condition(attribute=full_attr, operator=Operator.NOT_IN, value=vals)
                    )

                for op, threshold in info["ranges"]:
                    simplified_conditions.append(
                        Condition(attribute=full_attr, operator=op, value=threshold)
                    )

            if not simplified_conditions:
                # No conditions -> would match everything; skip degenerate rules
                return

            # Separate permission conditions (for action extraction) from attribute conditions
            permission_conds = [
                c for c in simplified_conditions
                if "permission" in c.attribute and "." not in c.attribute
            ]
            non_perm_conds = [c for c in simplified_conditions if c not in permission_conds]
            final_conditions = non_perm_conds if non_perm_conds else simplified_conditions

            if not final_conditions:
                return

            # Determine the action(s): one rule per permission (spec requirement)
            if permission_conds:
                # Permission was a split feature — extract the specific action(s)
                actions_from_path: List[str] = []
                for pc in permission_conds:
                    if pc.operator == Operator.EQ:
                        actions_from_path = [str(pc.value)]
                        break
                    elif pc.operator == Operator.IN:
                        actions_from_path = [str(v) for v in pc.value]
                        break
                if not actions_from_path:
                    actions_from_path = ["permit"]
            else:
                # Permission was NOT a split feature — path applies to ALL permissions
                # in covered positive samples. One rule per permission (spec requirement).
                if not samples.empty and "permission" in samples.columns:
                    covered = _apply_conditions_to_df(final_conditions, samples)
                    pos_covered = covered[covered["authorised"] == 1] if "authorised" in covered.columns else covered
                    if not pos_covered.empty:
                        actions_from_path = sorted(pos_covered["permission"].unique().tolist())
                    else:
                        actions_from_path = ["permit"]
                else:
                    actions_from_path = ["permit"]

            for action in actions_from_path:
                rule_counter += 1
                rule_id = f"R{rule_counter:03d}"

                # Compute support / confidence per action (TEMPORARY)
                support, confidence, n_cov_pos, n_cov_neg = _compute_support_confidence(
                    final_conditions, action, samples
                )

                if support < min_support or confidence < min_confidence:
                    logger.debug(
                        "Rule %s filtered: support=%.4f (min=%.4f), confidence=%.4f (min=%.4f)",
                        rule_id, support, min_support, confidence, min_confidence,
                    )
                    rule_counter -= 1
                    continue

                rule = ABACRule(
                    rule_id=rule_id,
                    effect="permit",
                    action=action,
                    conditions=final_conditions,
                    support=support,
                    confidence=confidence,
                    n_covered_positive=n_cov_pos,
                    n_covered_negative=n_cov_neg,
                    status=RuleStatus.CANDIDATE,
                    source="tree_path",
                    derived_from=[],
                )
                rules.append(rule)
            return

        # Internal node: recurse left and right
        feature_idx = int(tree_.feature[node_id])
        threshold = float(tree_.threshold[node_id])

        _walk(
            left_child,
            path_conditions + [{"feature": feature_idx, "direction": "left", "threshold": threshold}],
        )
        _walk(
            right_child,
            path_conditions + [{"feature": feature_idx, "direction": "right", "threshold": threshold}],
        )

    _walk(0, [])

    logger.info(
        "Extracted %d candidate rules (min_support=%.3f, min_confidence=%.3f)",
        len(rules), min_support, min_confidence,
    )
    return rules
