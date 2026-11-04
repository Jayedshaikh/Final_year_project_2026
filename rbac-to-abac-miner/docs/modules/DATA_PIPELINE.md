# Module: Data Pipeline

**Owner:** Jayed (`backend/data_pipeline/`). **Consumers:** `backend/ml_engine`, `backend/services`, Shweta's QA oracle.
**Related:** `docs/modules/DATA_CONTRACTS.md`, `docs/modules/VALIDATION.md`, `docs/development_rules/DECISIONS.md` (D-001, D-003).

Covers report layers 1 to 3: data collection, preprocessing, training-data generation.

## 1. Input files (six tables)

All files are UTF-8 with a header row and `snake_case` column names. CSV or JSON (JSON = an object with one array of records per table name; all six must use the same format).

| File | Required columns | Notes |
|---|---|---|
| `users` | `user_id` + attribute columns | Every non-id column is a **user attribute** (for example `department`, `position`, `seniority_years`) unless `user_attribute_columns` is given. |
| `roles` | `role_id` (+ optional `role_name`) | |
| `permissions` | `permission_id` (+ optional `description`) | Under D-001 the permission is an **action** such as `read`, `write`. |
| `user_roles` (UA) | `user_id`, `role_id` | |
| `role_permissions` (PA) | `role_id`, `permission_id`, optional `resource_id` | Blank or absent `resource_id` = the permission applies to **all** resources. D-001 is OPEN: confirm against the report in Milestone 2. |
| `resources` | `resource_id` + attribute columns | Every non-id column is a **resource attribute** (for example `type`, `sensitivity`, `department`). |

Identifiers are strings. Attribute names must not contain `.` (the prefixes `user.` and `resource.` are added by the pipeline).

## 2. Authorisation relation (Auth)

A tuple `(user_id, resource_id, permission)` is **authorised** iff there is a role `r` with `(user_id, r)` in UA and a PA row `(r, permission[, resource_id])` that covers `resource_id`.

`build_auth_matrix(dataset) -> DataFrame` returns the **full** matrix over `users x resources x permissions` with columns `user_id, resource_id, permission, authorised (0/1)`, sorted by the three keys so output is deterministic. Size is `|U| * |R| * |P|`; for the demo (about 200 x 100 x 3 = 60 000 rows) this is fine in memory.

Granthali's `verify_rbac_authorisation` and `build_access_matrix` must produce the **same** matrix. Shweta's oracle test compares both on the small dataset.

## 3. Preprocessing (layer 2)

`clean_attributes(df, config)`:
- strip whitespace, normalise categorical case (decision: lower-case for comparison, keep the original spelling in output rules via a lookup);
- missing values follow `config/mining_config.json -> preprocessing.missing_value_strategy` (default `"category_unknown"` for categoricals, `"median"` for numerics). The strategy is **reported**, never silent.
- dataset-level checks (dangling ids, duplicates) are **not** reimplemented here; call `data_engineering.data_validation` and surface its `ValidationIssue`s. If any `severity == "error"` exists, stop and return `status: invalid`.

`encode_features(train_df, test_df) -> (X_train, X_test, encoder)`:
- Features are the user attributes, resource attributes and `permission`. **Identifiers (`user_id`, `resource_id`) are never features.**
- Categorical: one-hot. Numeric: left numeric.
- The encoder is **fitted on the training split only** and then applied to the test split (no leakage).
- The encoder object must keep a map `feature_name -> (scope, attribute, category | None)` so `ml_engine.extract_rules` can decode tree splits back to readable conditions.

## 4. Training-data generation (layer 3)

`build_training_samples(auth_df, users, resources, ratio, seed) -> (samples_df, n_pos, n_neg)`:

1. `S+` = all tuples with `authorised == 1`.
2. `S-` = tuples with `authorised == 0`, sampled **without replacement** with `n_neg = min(ratio * n_pos, available)` using `numpy.random.default_rng(seed)`. `strategy="stratified"` samples proportionally per permission.
3. Join user and resource attributes. Columns: `user_id, resource_id, permission, user.<attr>..., resource.<attr>..., authorised`.
4. Stratified train/test split on `authorised` (default 80/20, `random_state = seed`).
5. Class imbalance: `class_weight="balanced"` for tree models by default; `imbalanced-learn` resampling is optional and applies to the **train split only**.

Edge cases that must return a clear `ErrorResponse` (never a crash, never a silent pass): empty dataset, zero positives, zero negatives (all-authorised data), single class after split, attribute column with only one distinct value (warn, keep).

## 5. Data handed to other modules

| Consumer | Object | Columns |
|---|---|---|
| `ml_engine` | `X_train, X_test, y_train, y_test, encoder` | encoded features, label `authorised` |
| `policy_engine.optimise_policy` | `samples_df` (decoded, **not** encoded) | `user_id, resource_id, permission, user.*, resource.*, authorised` |
| `policy_engine.validate_policy` | `access_matrix_df`, `user_attrs_df`, `resource_attrs_df` | matrix: `user_id, resource_id, permission, authorised`; attribute tables: `user_id` (or `resource_id`) + unprefixed attribute columns |

`access_matrix_df` is the **full** matrix from section 2. Validation on `samples_df` alone is forbidden (project rule).

## 6. Reproducibility

Every random operation takes the seed from the request (default 42). Same dataset + same config = byte-identical samples and metrics. Record seed, ratio and file hashes in the run record.

## 7. Tests (Jayed, `backend/tests/`)

- Auth matrix hand example (3 users, 2 roles, 3 resources) equals the hand-computed answer.
- Resource-scoped PA row grants only that resource; blank grants all.
- Sampling is deterministic for a seed and different for another seed; `n_neg` honours `ratio`.
- Split is stratified; encoder fitted on train only (assert test-only categories become all-zero, not new columns).
- Empty, all-authorised and single-class inputs raise the documented errors.
