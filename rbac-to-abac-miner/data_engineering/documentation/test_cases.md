# Test Cases Documentation

**Owner:** Shweta Suresh Kidile  
**Module:** `data_engineering/`, `tests/`  
**Related:** `docs/modules/VALIDATION.md`, `docs/modules/DATA_CONTRACTS.md`

All expected values in this document are **independently hand-computed** — never copied from model output (project rule RULE_12).

---

## 1. Authorisation Oracle — Worked Examples

### Example 1.1 — Tiny 3-user dataset (oracle cross-check)

**Input:**

| Table | Content |
|-------|---------|
| users | U001 (Finance, seniority=3), U002 (Finance, seniority=5), U003 (HR, seniority=7) |
| roles | R01 (Finance_Analyst), R02 (HR_Specialist) |
| permissions | read |
| resources | RES001 (Finance, low, report), RES002 (Finance, medium, document) |
| user_roles | U001→R01, U002→R01 *(U003 has no role)* |
| role_permissions | R01→read (all resources, resource_id=""), R02→read (all resources) |

**D-001 applied:** permission is an action; blank `resource_id` = all resources.

**Hand-computed authorisation matrix:**

| user_id | resource_id | permission | authorised | Reason |
|---------|-------------|------------|------------|--------|
| U001 | RES001 | read | **1** | U001 holds R01; R01 grants read on all resources |
| U001 | RES002 | read | **1** | Same path |
| U002 | RES001 | read | **1** | U002 holds R01 |
| U002 | RES002 | read | **1** | Same path |
| U003 | RES001 | read | **0** | U003 holds no role → no granting path |
| U003 | RES002 | read | **0** | Same |

**Expected summary:** n_authorised = 4, n_unauthorised = 2, n_total = 6  
**Authorisation density = 4/6 = 0.6667**

Corresponds to scenario file: `test_scenarios/tiny_3users.json`

---

### Example 1.2 — Scoped permission (D-001 resource_id present)

**Input (minimal):**

| Table | Content |
|-------|---------|
| users | U001 (Finance), U002 (HR) |
| roles | R01 |
| permissions | write |
| resources | RES001, RES002 |
| user_roles | U001→R01, U002→R01 |
| role_permissions | R01→write→**RES001** (scoped to RES001 only) |

**Hand-computed matrix:**

| user_id | resource_id | permission | authorised | Reason |
|---------|-------------|------------|------------|--------|
| U001 | RES001 | write | **1** | R01 grants write on RES001 specifically |
| U001 | RES002 | write | **0** | R01 write is scoped to RES001 only |
| U002 | RES001 | write | **1** | Same as U001 |
| U002 | RES002 | write | **0** | Same |

**Expected:** n_authorised = 2, n_unauthorised = 2, n_total = 4

---

### Example 1.3 — Multi-role user

**Input (minimal):**

| Table | Content |
|-------|---------|
| users | U001 |
| roles | R01, R02 |
| permissions | read, write |
| resources | RES001 |
| user_roles | U001→R01, U001→R02 |
| role_permissions | R01→read (all), R02→write→RES001 |

**Hand-computed matrix:**

| user_id | resource_id | permission | authorised | Reason |
|---------|-------------|------------|------------|--------|
| U001 | RES001 | read | **1** | Via R01 |
| U001 | RES001 | write | **1** | Via R02 (scoped to RES001) |

**Expected:** n_authorised = 2, n_unauthorised = 0  
Note: if resources included RES002, then (U001, RES002, write) = 0.

---

## 2. Policy Metrics — Hand-Computed Examples

Reference: `docs/modules/VALIDATION.md` §2

### Formulas

```
precision = TP / (TP + FP)            ; 0.0 if denominator is 0
recall    = TP / (TP + FN)            ; 0.0 if denominator is 0
F1        = 2 * precision * recall / (precision + recall)  ; 0.0 if sum is 0
OPR       = FP / (FP + TN)            ; over_privilege_rate ; 0.0 if denominator is 0
UPR       = FN / (FN + TP)            ; under_privilege_rate ; 0.0 if denominator is 0
```

Confusion matrix:

|  | RBAC authorised | RBAC not authorised |
|--|-----------------|---------------------|
| **ABAC permits** | TP | FP (over-privilege) |
| **ABAC denies**  | FN (under-privilege) | TN |

---

### Example 2.1 — From VALIDATION.md worked example

**Permission:** read, 3 users, 2 resources → 6 tuples.  
**RBAC authorised:** (u1,r1), (u2,r1), (u3,r2)  
**Policy permits:** (u1,r1), (u2,r1), (u1,r2)

**Confusion matrix:**

| Tuple | RBAC | Policy | Cell |
|-------|------|--------|------|
| (u1,r1) | 1 | 1 | TP |
| (u2,r1) | 1 | 1 | TP |
| (u3,r2) | 1 | 0 | FN |
| (u1,r2) | 0 | 1 | FP |
| (u2,r2) | 0 | 0 | TN |
| (u3,r1) | 0 | 0 | TN |

**Counts:** TP=2, FP=1, FN=1, TN=2

**Expected metrics:**

| Metric | Calculation | Value |
|--------|-------------|-------|
| precision | 2/(2+1) | **0.6667** |
| recall | 2/(2+1) | **0.6667** |
| F1 | 2*(2/3)*(2/3)/((2/3)+(2/3)) | **0.6667** |
| OPR | 1/(1+2) | **0.3333** |
| UPR | 1/(1+2) | **0.3333** |
| n_tuples_evaluated | 6 | **6** |
| over_privileged_example | (u1,r2) | |
| under_privileged_example | (u3,r2) | |

---

### Example 2.2 — Perfect policy (zero errors)

**RBAC authorised:** (U001,RES001,read), (U002,RES001,read)  
**RBAC not authorised:** (U003,RES001,read)  
**Policy permits:** exactly the same 2 tuples.

| Counts | Value |
|--------|-------|
| TP | 2 |
| FP | 0 |
| FN | 0 |
| TN | 1 |

| Metric | Calculation | Value |
|--------|-------------|-------|
| precision | 2/(2+0) | **1.0** |
| recall | 2/(2+0) | **1.0** |
| F1 | 2*1*1/(1+1) | **1.0** |
| OPR | 0/(0+1) | **0.0** |
| UPR | 0/(0+2) | **0.0** |
| n_tuples_evaluated | 3 | **3** |

---

### Example 2.3 — Over-permissive policy

**Setup:** 3 users (U1, U2, U3), 1 resource (R1), 1 permission (read).  
**RBAC authorised:** (U1,R1,read) only.  
**Policy:** permits ALL (blanket read permission).

| Counts | Value |
|--------|-------|
| TP | 1 |
| FP | 2 |
| FN | 0 |
| TN | 0 |

| Metric | Calculation | Value |
|--------|-------------|-------|
| precision | 1/(1+2) | **0.3333** |
| recall | 1/(1+0) | **1.0** |
| F1 | 2*(1/3)*1/((1/3)+1) | **0.5** |
| OPR | 2/(2+0) | **1.0** |
| UPR | 0/(0+1) | **0.0** |

---

## 3. WSC (Weighted Structural Complexity) — Hand Examples

**Formula** (from `POLICY_ENGINE.md` §5, `config/mining_config.json`):
```
WSC = Σ over rules of (w_rule + w_cond * n_conditions + w_val * total_elements_in_in/not_in_sets)
```
Default weights: `w_rule=1.0, w_cond=1.0, w_val=0.5`

### Example 3.1 — Single simple rule

**Rule:** `user.department == "Finance"` AND `resource.sensitivity in ["low", "medium"]`  
- n_conditions = 2
- `in` set has 2 elements → w_val contribution = 0.5 * 2 = 1.0
- WSC = 1 + 1*2 + 0.5*2 = **4.0**

### Example 3.2 — Two rules

**Rule 1:** `user.department == "Finance"` (1 condition, no in/not_in sets)  
WSC₁ = 1 + 1*1 + 0 = 2.0

**Rule 2:** `resource.type in ["report", "document", "database"]` (1 condition, in-set of 3)  
WSC₂ = 1 + 1*1 + 0.5*3 = 3.5

**Total WSC = 2.0 + 3.5 = 5.5**

---

## 4. Validation Issue Code — Test Coverage Table

| Test ID | Issue Code | Severity | Scenario File | Test Function | Status |
|---------|------------|----------|---------------|---------------|--------|
| TC-V-01 | `MISSING_FILE` | error | *(dict with missing key)* | `test_missing_file` | planned |
| TC-V-02 | `EMPTY_FILE` | error | `empty_users.json` | `test_empty_file` | planned |
| TC-V-03 | `MISSING_COLUMN` | error | *(users without user_id)* | `test_missing_required_column` | planned |
| TC-V-04 | `DUPLICATE_KEY` | error | `duplicate_user_id.json` | `test_duplicate_key` | planned |
| TC-V-05 | `DUPLICATE_RECORD` | warning | `duplicate_record_ua.json` | `test_duplicate_record` | planned |
| TC-V-06 | `DANGLING_REFERENCE` | error | `dangling_role_reference.json` | `test_dangling_reference` | planned |
| TC-V-07 | `MISSING_VALUE` | warning | `missing_value.json` | `test_missing_value` | planned |
| TC-V-08 | `INVALID_TYPE` | error | `invalid_type_seniority.json` | `test_invalid_type` | planned |
| TC-V-09 | `INVALID_VALUE` | warning | `invalid_value_negative.json` | `test_invalid_value` | planned |
| TC-V-10 | `USER_WITHOUT_ROLE` | warning | `user_no_roles.json` | `test_user_without_role` | planned |
| TC-V-11 | `ROLE_WITHOUT_PERMISSION` | warning | `role_no_permissions.json` | `test_role_without_permission` | planned |
| TC-V-12 | `SINGLE_CLASS` (all +) | error | `all_authorised.json` | `test_single_class_all_positive` | planned |
| TC-V-13 | `SINGLE_CLASS` (all -) | error | `none_authorised.json` | `test_single_class_all_negative` | planned |
| TC-V-14 | No issues | — | `small` dataset | `test_valid_small_dataset` | planned |
| TC-V-15 | Unicode | — | `unicode_names.json` | `test_unicode_names` | planned |

---

## 5. Dataset Generation Tests

| Test ID | Description | Expected | Test Function |
|---------|-------------|----------|---------------|
| TC-G-01 | Same seed → identical files | Byte-identical CSV output | `test_determinism_same_seed` |
| TC-G-02 | Different seeds → different data | At least one difference | `test_different_seeds_differ` |
| TC-G-03 | Small size has correct shape | 12 users, 4 roles, 3 perms, 8 resources | `test_small_dataset_shape` |
| TC-G-04 | Medium size has correct shape | 200 users, 8 roles, 5 perms, 100 resources | `test_medium_dataset_shape` |
| TC-G-05 | All 6 CSV files generated | All filenames present | `test_all_files_generated` |
| TC-G-06 | JSON has same data as CSVs | Record counts match | `test_json_matches_csv` |
| TC-G-07 | Required columns present | Per DATA_PIPELINE.md §1 | `test_required_columns` |
| TC-G-08 | Unknown size raises ValueError | ValueError raised | `test_unknown_size_error` |

---

## 6. Oracle Tests

| Test ID | Description | Expected | Test Function |
|---------|-------------|----------|---------------|
| TC-O-01 | 3-user hand example (Example 1.1) | n_auth=4, n_unauth=2 | `test_oracle_tiny_3users` |
| TC-O-02 | Scoped permission (Example 1.2) | n_auth=2, n_unauth=2 | `test_oracle_scoped_permission` |
| TC-O-03 | Multi-role user (Example 1.3) | n_auth=2, n_unauth=0 | `test_oracle_multi_role_user` |
| TC-O-04 | Output columns correct | ['user_id','resource_id','permission','authorised'] | `test_oracle_output_columns` |
| TC-O-05 | Output sorted deterministically | Same input → same row order | `test_oracle_sorted_output` |
| TC-O-06 | User with no role → all 0 | authorised=0 for all tuples | `test_oracle_user_no_role` |
| TC-O-07 | Oracle covers all N×R×P tuples | n_rows = n_users * n_resources * n_permissions | `test_oracle_full_coverage` |

---

## 7. API and Integration Tests

| Test ID | Description | Backend needed | Test Function |
|---------|-------------|----------------|---------------|
| TC-A-01 | All shared/sample_responses/*.json validate against Pydantic models | No | `test_mock_responses_valid` |
| TC-A-02 | POST /api/v1/datasets/upload returns DatasetValidationResponse | Yes (skipif) | `test_upload_endpoint` |
| TC-A-03 | GET /api/v1/datasets/{id}/authorisation returns RBACAuthorisationResponse | Yes (skipif) | `test_authorisation_endpoint` |
| TC-A-04 | POST /api/v1/training/run returns TrainingResponse | Yes (skipif) | `test_training_endpoint` |
| TC-A-05 | GET /api/v1/training/{run_id}/comparison returns ModelComparisonResponse | Yes (skipif) | `test_comparison_endpoint` |
| TC-A-06 | GET /api/v1/training/{run_id}/rules returns ExtractedRulesResponse | Yes (skipif) | `test_rules_endpoint` |
| TC-A-07 | Error response shape matches ErrorResponse | No | `test_error_response_shape` |
| TC-I-01 | Oracle matches auth matrix on small dataset (cross-check Jayed) | Yes (skipif until M3) | `test_oracle_matches_backend` |
| TC-I-02 | verify_samples passes on a correct samples_df | No | `test_verify_samples_correct` |
| TC-I-03 | verify_samples catches wrong positive label | No | `test_verify_samples_wrong_positive` |
| TC-I-04 | verify_samples catches wrong negative label | No | `test_verify_samples_wrong_negative` |
| TC-I-05 | End-to-end upload → validate → auth matrix flow | Yes (skipif until M10) | `test_end_to_end_flow` |

---

## 8. Implementation Decisions Noted Here

**D-001 (permission model):** Implemented as — `permission_id` is an action string; `role_permissions.csv` has an optional `resource_id` column (blank = all resources). This matches the proposed default in `DECISIONS.md` and the contract examples. Must be confirmed against the report PDF by Jayed, Granthali and Shweta.

> This note is informational only. Shweta does not have write access to `DECISIONS.md` (owned by Jayed). Jayed should formally record the resolution there.
