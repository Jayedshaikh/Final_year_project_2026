# Module: Validation (data validation and policy validation)

Two kinds of validation exist. Do not mix them up.

| Kind | What is checked | Owner | Code |
|---|---|---|---|
| Dataset validation | Uploaded RBAC tables are consistent | Shweta | `data_engineering/data_validation/` |
| Policy validation | Mined ABAC policy vs the original RBAC authorisation state | Granthali | `policy_engine/policy_validator/` |

## 1. Dataset validation (layer 2)

`data_engineering.data_validation` is importable **without** the backend. Public function (Shweta defines, Jayed calls):

```python
# data_engineering/data_validation/validator.py
validate_dataset(files: dict[str, pd.DataFrame]) -> list[dict]
# each dict has exactly the ValidationIssue fields: severity, code, file, row, column, message
# (Jayed wraps them: ValidationIssue(**d) from shared/schemas/contracts.py)
```

Issue codes (`ValidationIssue.code`):

| Code | Severity | Meaning |
|---|---|---|
| `EMPTY_FILE` | error | A required table has no rows |
| `MISSING_FILE` | error | One of the six tables was not provided |
| `MISSING_COLUMN` | error | Required column absent (see DATA_PIPELINE.md section 1) |
| `DUPLICATE_KEY` | error | Repeated `user_id`, `role_id`, `permission_id` or `resource_id` |
| `DUPLICATE_RECORD` | warning | Repeated UA or PA row (deduplicated) |
| `DANGLING_REFERENCE` | error | UA/PA row points to an unknown user, role, permission or resource |
| `MISSING_VALUE` | warning | Empty attribute value (handled by the configured strategy) |
| `INVALID_TYPE` | error | Non-numeric value in a column that is otherwise numeric |
| `INVALID_VALUE` | warning | Value out of range, for example negative `seniority_years` |
| `USER_WITHOUT_ROLE` | warning | User has no role, so is never authorised |
| `ROLE_WITHOUT_PERMISSION` | warning | Role grants nothing |
| `SINGLE_CLASS` | error | All tuples authorised, or none, so a classifier cannot be trained |

Any `error` makes the response `status: "invalid"` with `dataset_id: null`.

## 2. Policy validation (layer 6)

Always performed against the **full access matrix**, never only the sampled training set. Result type: `PolicyMetrics` (`evaluated_on = "full_access_matrix"`).

For every tuple in the matrix, the policy decision is `permit` or `deny` (default deny); RBAC truth is `authorised`.

| | RBAC authorised | RBAC not authorised |
|---|---|---|
| ABAC permits | TP | FP (over-privilege) |
| ABAC denies | FN (under-privilege) | TN |

Definitions (implementation decision D-002, **confirm against the report**):

- `precision = TP / (TP + FP)`; `recall = TP / (TP + FN)`; `F1 = 2PR / (P + R)`.
- `OPR (over_privilege_rate) = FP / (FP + TN)`: share of RBAC-unauthorised tuples the policy wrongly permits.
- `UPR (under_privilege_rate) = FN / (FN + TP)`: share of RBAC-authorised tuples the policy wrongly denies.
- `rule_count`, `wsc` (see POLICY_ENGINE.md section 5), `n_tuples_evaluated = TP + FP + FN + TN`.
- Any zero denominator gives `0.0` for that metric (and F1 is `0.0` when precision + recall is 0). Never raise, never return NaN.

### Worked example (use it as the first test)

Permission `read`; 3 users, 2 resources, so 6 tuples.

- RBAC authorised: `(u1,r1)`, `(u2,r1)`, `(u3,r2)`.
- Policy permits: `(u1,r1)`, `(u2,r1)`, `(u1,r2)`.

Counts: TP = 2 (`u1,r1`; `u2,r1`), FP = 1 (`u1,r2`), FN = 1 (`u3,r2`), TN = 2 (`u2,r2`; `u3,r1`).

Expected: precision = 2/3, recall = 2/3, F1 = 2/3, OPR = 1/3, UPR = 1/3, `n_tuples_evaluated = 6`. Over-privileged example: `(u1,r2)`; under-privileged example: `(u3,r2)`.

WSC example (defaults 1, 1, 0.5): one rule with 2 conditions, one of them `in ["a","b","c"]` gives `1 + 1*2 + 0.5*3 = 4.5`.

Shweta supplies at least two more hand-computed examples in `data_engineering/documentation/test_cases.md`; Granthali's validator must reproduce them exactly.

## 3. Model-level metrics vs policy-level metrics

`ModelMetrics` (test split of the sampled dataset) are classifier accuracy references. `PolicyMetrics` (full matrix) describe the final ABAC policy. Never present one as the other. The UI labels them separately.

## 4. Fail-safe validation behaviour

If evaluating a rule raises or a rule is malformed, that rule contributes **no permit**. If validation itself cannot complete, the API returns an `ErrorResponse` (HTTP 500) and no export is allowed. Under no circumstances may an error path produce a permit.

## 5. Acceptance checks for the whole system

1. Auth matrix from Jayed equals the matrix from Granthali on the small dataset.
2. Worked example reproduces exactly.
3. Re-running with the same seed reproduces all numbers.
4. No policy metric in a response was computed on sampled negatives only.
5. Export refuses unapproved rules.
