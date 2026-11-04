# Development Guide — Granthali Sandesh Mahajan

**Designation:** Security Logic and ABAC Policy Engineer
**Branch:** `feature/granthali-policy-engine`
**Hardware:** Low-specification laptop. Your modules are lightweight Python + pandas. You never train ML models.

## 1. Primary objective

Own everything that happens to a rule after it is extracted: defining the ABAC rule structure, evaluating rules, computing support and confidence, merging, generalising and pruning rules, validating the final policy against the full RBAC access matrix, computing WSC, and exporting approved rules as JSON and XACML-style XML. Jayed extracts candidate rules from the Decision Tree; you optimise, validate and export them.

## 2. Exact module ownership (OWNER)

```
policy_engine/
├── __init__.py            public API: optimise_policy, validate_policy, export_policy, verify_rbac_authorisation
├── schemas/               rule model, evaluation, config
├── rule_merger/
├── rule_generalizer/
├── rule_pruner/
├── policy_validator/
├── policy_exporter/
├── tests/
└── README.md
```

Read-only for you: everything else. You may propose `config/` keys through a PR reviewed by Jayed. `policy_engine` must never import from `backend`.

## 3. Responsibilities

1. Understand RBAC and ABAC.
2. RBAC authorisation verification logic.
3. ABAC rule structure.
4. Rule merging and generalisation.
5. Detect redundant and overly specific rules.
6. Rule pruning.
7. Support and confidence.
8. Policy validation logic.
9. Weighted Structural Complexity (WSC).
10. JSON policy export and XACML-style representation.
11. Security test scenarios.

## 4. Tasks in implementation order

### Task 1 — Rule schema and evaluation (Milestone 7, days 1-3)
`policy_engine/schemas/rule.py`: use `ABACRule` and `Condition` from `shared/schemas/contracts.py` (import it; do not copy). Implement `evaluate_condition(cond, user_attrs, resource_attrs) -> bool` and `rule_matches(rule, user_attrs, resource_attrs, action) -> bool`.

Fail-safe: a missing attribute, wrong type or unknown operator returns `False` (deny) and never raises through the public API.

### Task 2 — RBAC authorisation verification
`policy_engine/schemas/rbac.py`: `verify_rbac_authorisation(ua, pa, user_id, permission) -> bool` and `build_access_matrix(users, resources, ua, pa, permissions) -> DataFrame` with columns `user_id, resource_id, permission, authorised`. Co-develop with Jayed's `build_auth_matrix`; the two must agree, and Shweta's oracle checks both.

### Task 3 — Support and confidence
`policy_engine/schemas/metrics.py`:
- `support(rule, samples) = rows matched by rule / total rows` (state exact definition in `POLICY_ENGINE.md` and match the report's definition; flag any mismatch).
- `confidence(rule, samples) = positives matched / rows matched`.
Return 0.0 for rules matching nothing (no division by zero).

### Task 4 — Merging, generalisation, pruning (Milestone 7)
- `rule_merger/merger.py` `merge_rules(rules, samples, cfg)`: merge rules that differ in exactly one condition on the same attribute (union values into an `in` set or widen a numeric threshold) when the merged rule keeps confidence at or above `min_confidence`. Record `derived_from` and `source="merged"`.
- `rule_generalizer/generalizer.py` `generalise_rules(rules, samples, cfg)`: remove a condition only when doing so does not drop confidence below threshold and does not add negatives beyond the tolerance. Safe, evidence-based removal only.
- `rule_pruner/pruner.py` `prune_rules(rules, samples, cfg)`: drop rules whose coverage of positives is fully covered by other rules (redundant), and rules below minimum support.
- Each step reports counts for `OptimisationSummary`.

### Task 5 — Validation and metrics (Milestone 8)
`policy_validator/validator.py`:
`validate_policy(rules, access_matrix_df, user_attrs_df, resource_attrs_df) -> (PolicyMetrics, over_examples, under_examples)`.
Evaluate every tuple in the **full** matrix. Definitions (confirm against the report and record in `VALIDATION.md`):
- TP = permitted by policy and by RBAC; FP = permitted by policy, not by RBAC; FN = permitted by RBAC, not by policy.
- precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = harmonic mean.
- OPR = FP / number of RBAC-unauthorised tuples; UPR = FN / number of RBAC-authorised tuples (confirm the denominators in the report).
- rule_count; WSC (Task 6).
Handle zero denominators explicitly. Default decision is deny.

### Task 6 — WSC
`policy_validator/wsc.py`: `weighted_structural_complexity(rules, weights=None) -> float`. Use the report's formula if given. If the report is silent, use an implementation decision such as: sum over rules of (w_rule + w_cond x number of conditions + w_val x total values in `in` sets) with default weights 1, 1, 0.5, configurable in `config/`. Record it in `DECISIONS.md`.

### Task 7 — Export (Milestone 11)
`policy_exporter/exporter.py`: `export_policy(rules, fmt, policy_id) -> str`.
- Raises `ValueError` if no rule has `status == "approved"`; silently skipping unapproved rules is allowed, but exporting them is not.
- JSON: `{ "policy_id", "default_decision": "deny", "rules": [...] }`.
- XACML-style: `Policy` with `RuleCombiningAlgId` permit-overrides (or deny-unless-permit), one `Rule Effect="Permit"` per approved rule with `Target` and `Condition` built from attribute designators, and a final default deny rule. It is "XACML-style" (a readable representation), not a certified XACML 3.0 implementation.

### Task 8 — Public API and integration
`policy_engine/__init__.py` exports:
```python
optimise_policy(rules, samples_df, config) -> tuple[list[ABACRule], OptimisationSummary]
validate_policy(rules, access_matrix_df, user_attrs_df, resource_attrs_df) -> tuple[PolicyMetrics, list, list]
export_policy(rules, fmt, policy_id) -> str
verify_rbac_authorisation(...)
```
Do not rename these without approval. Jayed calls them from `backend/services/`.

### Task 9 — Security test scenarios
Tests: missing attribute denies, malformed rule denies, exception during evaluation denies, over-privilege detected, under-privilege detected, unapproved rule not exported, empty policy denies everything, conflicting merge refused, idempotence of pruning.

## 5. Required files

As listed in section 2, plus `policy_engine/README.md` and tests per module.

## 6. Input and output contracts

`ABACRule`, `Condition`, `PolicyMetrics`, `OptimisationSummary`, `ExportResponse` content format in `shared/schemas/contracts.py`. Detailed signatures: `docs/modules/POLICY_ENGINE.md`.

## 7. Dependencies

`pandas`, `numpy`, `pydantic>=2`, `pytest`. No scikit-learn, no FastAPI.

## 8. Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pandas numpy "pydantic>=2" pytest
```

## 9. Commands

```bash
python -m pytest policy_engine/tests -q
python scripts/validate_governance.py
```

## 10. Testing instructions

Develop against tiny hand-made data (5-10 rows) and Shweta's `small` dataset. For each function, compute the expected answer by hand and put the reasoning in a comment in the test. Test boundary values of operators and the zero-denominator cases.

## 11. Integration instructions

1. Agree the signatures above with Jayed on day 1, then implement against them.
2. Ask Shweta for a hand-computed validation example and make your validator reproduce it.
3. When you change a signature or a metric definition, update `POLICY_ENGINE.md` and tell Jayed before merging.

## 12. Restrictions

- Do not train ML models or edit Jayed's pipeline.
- Do not import from `backend`; the dependency direction is backend to policy_engine only.
- Never export unapproved rules; never auto-approve; never default to allow.
- Do not edit `shared/` (request a change instead).

## 13. Completion criteria

- All public functions implemented and tested.
- A hand-computed example reproduces exactly in `validate_policy`.
- Optimisation reduces rule count or WSC on the sample data without lowering F1 below the configured tolerance, and reports before/after numbers honestly.
- Export works in both formats and refuses unapproved rules.
- `policy_engine/README.md` and `docs/modules/POLICY_ENGINE.md` accurate.

## 14. Common mistakes to avoid

- Validating on sampled data only.
- Merging rules that raise over-privilege beyond the tolerance.
- Letting an exception in rule evaluation turn into allow.
- Importing backend code and creating a circular dependency.
- Changing field names in the exported JSON after the frontend uses them.
