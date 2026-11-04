# Module: Data Pipeline

**Owner:** Jayed (`backend/data_pipeline/`). **Consumers:** `backend/ml_engine`, `backend/services`, Shweta's QA oracle.
**Related:** `docs/modules/DATA_CONTRACTS.md`, `docs/modules/VALIDATION.md`, `docs/development_rules/DECISIONS.md` (D-001, D-003).

Covers report layers 1 to 3: data collection, preprocessing, training-data generation.

## Implementation status

| File | Function | Status |
|---|---|---|
| `loader.py` | `load_rbac_dataset(files, fmt, ...)` | ✅ Complete |
| `auth_matrix.py` | `build_auth_matrix(dataset)` | ✅ Complete |
| `auth_matrix.py` | `get_authorisation_roles(dataset, user, resource, perm)` | ✅ Complete |
| `preprocess.py` | `clean_attributes(df, config)` | ✅ Complete |
| `preprocess.py` | `encode_features(train_df, test_df, ...)` | ✅ Complete |
| `sampling.py` | `build_training_samples(auth_df, users, resources, ...)` | ✅ Complete |
| `sampling.py` | `stratified_split(samples_df, ...)` | ✅ Complete |

## 1. Input files (six tables)

All files are UTF-8 with a header row and `snake_case` column names. CSV or JSON (JSON = an object with one array of records per table name; all six must use the same format).

| File | Required columns | Notes |
|---|---|---|
| `users` | `user_id` + attribute columns | Every non-id column is a **user attribute** (e.g. `department`, `position`, `seniority_years`) unless `user_attribute_columns` is given. |
| `roles` | `role_id` (+ optional `role_name`) | |
| `permissions` | `permission_id` (+ optional `description`) | Under D-001 the permission is an **action** such as `read`, `write`. |
| `user_roles` (UA) | `user_id`, `role_id` | |
| `role_permissions` (PA) | `role_id`, `permission_id`, optional `resource_id` | Blank or absent `resource_id` = the permission applies to **all** resources. D-001 CLOSED. |
| `resources` | `resource_id` + attribute columns | Every non-id column is a **resource attribute** (e.g. `type`, `sensitivity`, `department`). |

Identifiers are strings. Attribute names must not contain `.` (the prefixes `user.` and `resource.` are added by the pipeline).

## 2. Authorisation relation (Auth)

A tuple `(user_id, resource_id, permission)` is **authorised** iff there is a role `r` with `(user_id, r)` in UA and a PA row `(r, permission[, resource_id])` that covers `resource_id`.

`build_auth_matrix(dataset) -> DataFrame` returns the **full** matrix over `users x resources x permissions` with columns `user_id, resource_id, permission, authorised (0/1)`, sorted by the three keys so output is deterministic.

**Seed-hospital example:** 12 users × 8 resources × 3 permissions = 288 tuples, 200 authorised (density 0.694).

Granthali's `verify_rbac_authorisation` and `build_access_matrix` must produce the **same** matrix. Shweta's oracle test compares both on the small dataset.

## 3. Preprocessing (layer 2)

`clean_attributes(df, config)`:
- Strips whitespace, normalises categorical case (lower-case for comparison).
- Tries numeric coercion on every column: string columns that parse fully as numbers become float (handles CSV-loaded integers/floats arriving as strings).
- Missing values follow `config/mining_config.json → preprocessing.missing_value_strategy` (default `"category_unknown"` for categoricals, `"median"` for numerics). The strategy is **reported**, never silent.
- Dataset-level structural checks (dangling ids, duplicates) should be delegated to `data_engineering.data_validation` if available.

`encode_features(train_df, test_df) -> (X_train, X_test, encoder)`:
- Features: all columns except `user_id`, `resource_id`, `authorised`.
- Categorical: one-hot via `sklearn.preprocessing.OneHotEncoder(handle_unknown="ignore")`.
- Numeric: passed through as float32.
- Encoder fitted on **training data only** (no leakage).
- `FeatureEncoder.feature_map`: maps encoded column index → `(scope, attribute, category | None)` so `ml_engine.extract_rules` can decode tree splits.

## 4. Training-data generation (layer 3)

`build_training_samples(auth_df, users, resources, ratio, seed)`:

1. `S+` = all tuples with `authorised == 1`.
2. `S-` = tuples with `authorised == 0`, sampled **without replacement** with `n_neg = min(ratio * n_pos, available)` using `numpy.random.default_rng(seed)`. `strategy="stratified"` samples proportionally per permission.
3. Joins user and resource attributes. Columns: `user_id, resource_id, permission, user.<attr>..., resource.<attr>..., authorised`.
4. Stratified train/test split on `authorised` (default 80/20, `random_state = seed`).

Edge cases that raise `ValueError` with a clear message: empty dataset, zero positives, zero negatives (all-authorised data), single class after split.

## 5. Data handed to other modules

| Consumer | Object | Columns |
|---|---|---|
| `ml_engine` | `X_train, X_test, y_train, y_test, encoder` | encoded features, label `authorised` |
| `policy_engine.optimise_policy` | `samples_df` (decoded, **not** encoded) | `user_id, resource_id, permission, user.*, resource.*, authorised` |
| `policy_engine.validate_policy` | `access_matrix_df`, `user_attrs_df`, `resource_attrs_df` | matrix: `user_id, resource_id, permission, authorised`; attribute tables: key + unprefixed attribute columns |

`access_matrix_df` is the **full** matrix from section 2. Validation on `samples_df` alone is forbidden (project rule).

## 6. Reproducibility

Every random operation takes the seed from the request (default 42). Same dataset + same config = byte-identical samples and metrics. Verified by unit tests in `backend/tests/test_data_pipeline.py`.

## 7. Tests (`backend/tests/test_data_pipeline.py`)

- Auth matrix hand example (3 users, 2 roles, 3 resources) equals the hand-computed answer. ✅
- Resource-scoped PA row grants only that resource; blank grants all. ✅
- Sampling is deterministic for a seed and different for another seed. ✅
- Split is stratified; encoder fitted on train only. ✅
- Empty, all-authorised and single-class inputs raise documented errors. ✅
