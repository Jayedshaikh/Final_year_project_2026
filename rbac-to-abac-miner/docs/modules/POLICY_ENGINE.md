# Module: Policy Engine

**Owner:** Granthali (`policy_engine/`). **Caller:** Jayed's `backend/services/`. Report layers 5 (optimisation), 6 and 7 (export).
**Dependency direction:** `backend -> policy_engine -> shared`. `policy_engine` must never import `backend`, scikit-learn or FastAPI.

## 1. Integration interface (frozen unless all members approve)

```python
# policy_engine/__init__.py
from policy_engine import optimise_policy, validate_policy, export_policy, verify_rbac_authorisation

def optimise_policy(rules: list[ABACRule], samples_df: pd.DataFrame,
                    config: OptimisationConfig) -> tuple[list[ABACRule], OptimisationSummary]: ...

def validate_policy(rules: list[ABACRule], access_matrix_df: pd.DataFrame,
                    user_attrs_df: pd.DataFrame, resource_attrs_df: pd.DataFrame
                    ) -> tuple[PolicyMetrics, list[AuthorisationTuple], list[AuthorisationTuple]]: ...
                    # returns (metrics, over_privileged_examples, under_privileged_examples)

def export_policy(rules: list[ABACRule], fmt: str, policy_id: str) -> str: ...   # fmt: "json" | "xacml"

def verify_rbac_authorisation(ua: pd.DataFrame, pa: pd.DataFrame, user_id: str,
                              resource_id: str, permission: str) -> bool: ...
```

`ABACRule`, `Condition`, `PolicyMetrics`, `OptimisationSummary`, `AuthorisationTuple` are imported from `shared/schemas/contracts.py`. Do not redefine them. `OptimisationConfig` (a Pydantic model in `policy_engine/schemas/config.py`) has: `min_support`, `min_confidence`, `confidence_tolerance` (default 0.0), `wsc_weights` (see 5), `random_seed`. Jayed builds it from `TrainingConfigRequest` and `config/mining_config.json`.

Input frames (produced by Jayed, see DATA_PIPELINE.md section 5):
- `samples_df`: decoded values, columns `user_id, resource_id, permission, user.<attr>..., resource.<attr>..., authorised`.
- `access_matrix_df`: **full** matrix `user_id, resource_id, permission, authorised`.
- `user_attrs_df`, `resource_attrs_df`: key column plus unprefixed attribute columns.

## 2. Rule semantics

- A rule `permit`s tuple `(u, r, p)` iff `p == rule.action` **and** every condition holds on the attributes of `u` (prefix `user.`) and `r` (prefix `resource.`).
- A policy permits a tuple iff **any** counted rule permits it. Otherwise **deny** (closed world).
- Counted rules for validation: status in `candidate, optimised, approved, edited`; `rejected` rules are excluded (decision D-010). Export uses `approved` only.
- Operators: `==`, `!=`, `in`, `not_in`, `<=`, `<`, `>`, `>=`. Comparison operators need numeric values on both sides.
- **Fail safe:** missing attribute, null, type mismatch, unknown operator, malformed rule or any exception during evaluation means the rule does **not** match (deny). Public functions never raise out of an evaluation path; they log and deny.

## 3. Support and confidence (D-002: confirm with the report)

On a frame `F` of tuples with labels:
- `matched(rule) = rows in F where rule matches`
- `support = |matched| / |F|`
- `confidence = |matched with authorised == 1| / |matched|`, and `0.0` when `|matched| == 0`.

Because `samples_df` contains sampled negatives, support and confidence on samples are estimates. The final numbers shown to the administrator must be recomputed against the full matrix. Record whichever definition the report uses in `VALIDATION.md` if it differs.

## 4. Optimisation pipeline (`optimise_policy`)

Order: filter, merge, generalise, prune. Each step records counts for `OptimisationSummary` (`n_merged`, `n_generalised`, `n_pruned_redundant`, `rules_before/after`, `wsc_before/after`).

1. **Filter** rules below `min_support` or `min_confidence`.
2. **Merge** (`rule_merger/merger.py`): two rules with the same `action` and identical conditions except for one attribute are merged: `==` values become an `in` set, numeric thresholds widen to the looser bound. Accept only if merged confidence on `samples_df` is `>= min_confidence - confidence_tolerance`. New rule: `source="merged"`, `derived_from=[parent ids]`, status `optimised`.
3. **Generalise** (`rule_generalizer/generalizer.py`): drop one condition at a time only when confidence stays above threshold and added negatives are within tolerance. `source="generalised"`.
4. **Prune** (`rule_pruner/pruner.py`): remove a rule whose matched positives are a subset of the positives matched by the remaining rules (redundant), and rules below minimum support. Pruning twice gives the same result (idempotent).
5. Re-number nothing: surviving rules keep their ids; new merged rules get new ids (`M001`, ...).

Never accept a step that makes the policy permit tuples the evidence does not support beyond tolerance. Conflicting merges (different actions, contradictory conditions) are refused, not forced.

## 5. WSC (D-002)

`weighted_structural_complexity(rules, weights=None) -> float` default (implementation decision, replace with the report's formula if it differs):

`WSC = sum over rules of ( w_rule + w_cond * n_conditions + w_val * total_elements_in_in/not_in_sets )` with defaults `w_rule=1, w_cond=1, w_val=0.5`. Weights live in `config/mining_config.json -> wsc_weights`.

## 6. Export (`export_policy`)

- Only rules with `status == "approved"` are exported. If none are approved, raise `ValueError("no approved rules")` (the API turns this into HTTP 409).
- **JSON:** `{"policy_id", "default_decision": "deny", "generated_at", "rules": [{"rule_id","effect","action","conditions":[...],"support","confidence"}]}` (key order stable, `indent=2`).
- **XACML-style XML:** one `<Policy PolicyId=... RuleCombiningAlgId="...permit-overrides">`, one `<Rule Effect="Permit">` per approved rule with a `<Target>` for the action and a `<Condition>` that ANDs attribute comparisons (`user.x` as subject category, `resource.x` as resource category), and a final `<Rule Effect="Deny">` default. It is a readable XACML-style representation, **not** certified XACML 3.0.
- Output must parse (`json.loads` / `xml.etree`) in tests.

## 7. Required tests (`policy_engine/tests/`)

Operator boundaries, missing attribute denies, malformed rule denies, exception denies, empty policy denies all, over- and under-privilege detection, hand-computed metrics example from `docs/modules/VALIDATION.md`, merge accepted and refused cases, pruning idempotence, unapproved rule never exported, both export formats parse.
