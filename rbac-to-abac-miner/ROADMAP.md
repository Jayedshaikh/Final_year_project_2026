# ROADMAP.md — 12 Milestones

First target: **one thin end-to-end workflow** (upload, samples, Decision Tree, at least one rule, validate, display, export approved rule as JSON). Then add Random Forest, Gradient Boosting, optimisation and reporting.

## First seven days (initial allocation, not a promise of completion)

| Day | Jayed | Naeem | Shweta | Granthali |
|---|---|---|---|---|
| 1 | Backend skeleton, GitHub setup | UI architecture, scaffold | Dataset analysis | ABAC rule schema |
| 2 | RBAC loader, stub endpoints | Dashboard layout | Sample CSVs (small) | Rule representation, evaluation |
| 3 | Access matrix | Upload page | Data validation | Rule validation, support/confidence |
| 4 | Dataset generator (samples) | Dataset preview | Test cases, oracle | Rule merging |
| 5 | Basic Decision Tree | Mock API integration | API tests | Rule pruning |
| 6 | Model evaluation | Metrics dashboard | Pipeline testing | JSON exporter |
| 7 | Integration | Integration | Testing | Integration |

## Milestones

### M1 — Repository and project configuration (Jayed)
- Tasks: push scaffold, branches, branch protection, CODEOWNERS, CI.
- Depends on: none. Output: repo ready, everyone has a branch.
- Acceptance: all four can clone, branch and open a PR; CI passes. Testing: `scripts/validate_governance.py`.

### M2 — Sample datasets and data contracts (Shweta; contracts: all)
- Tasks: generator, small/medium CSV+JSON, validator, settle D-001/D-002.
- Depends on: M1. Output: `data_engineering/sample_datasets/`, `data_validation/`.
- Acceptance: reproducible from seed; validator catches every planted defect. Testing: `tests/test_data_validation.py`, `test_dataset_generation.py`.

### M3 — Data loading and RBAC authorisation matrix (Jayed, with Granthali)
- Tasks: loader, `build_auth_matrix`, Granthali's `build_access_matrix`.
- Depends on: M2. Output: Auth relation.
- Acceptance: Jayed's, Granthali's and Shweta's oracle matrices are identical on all samples. Testing: matrix equality test.

### M4 — Positive and negative dataset generation (Jayed)
- Tasks: S+, S-, attribute join, stratified split, encoding fitted on train only.
- Depends on: M3. Output: `samples_df`, train/test.
- Acceptance: Shweta's `verify_samples` passes; deterministic with seed. Testing: leakage and determinism tests.

### M5 — Machine learning training (Jayed)
- Tasks: DT, RF, GB, CV, tuning, evaluation, serialisation.
- Depends on: M4. Output: `TrainingResponse`, `ModelComparisonResponse`.
- Acceptance: metrics match independent recomputation by Shweta; same seed gives same result. Testing: ML unit tests on tiny data.

### M6 — Decision Tree rule extraction (Jayed)
- Tasks: permit paths to `ABACRule`, support, confidence, threshold filtering.
- Depends on: M5. Output: `ExtractedRulesResponse`.
- Acceptance: rules reproduce the tree's permit predictions on training data. Testing: rule-vs-tree equivalence test.

### M7 — Rule optimisation (Granthali)
- Tasks: merge, generalise, prune; `optimise_policy`.
- Depends on: M6 interface (can start earlier on hand-made rules). Output: `OptimisedPolicyResponse` content.
- Acceptance: rule count/WSC reduced without F1 loss beyond tolerance; idempotent. Testing: policy_engine unit tests.

### M8 — Policy validation and metrics (Granthali)
- Tasks: `validate_policy`, OPR, UPR, WSC, examples.
- Depends on: M3, M7. Output: `PolicyValidationResponse`.
- Acceptance: Shweta's hand-computed example reproduces exactly. Testing: metric tests.

### M9 — Frontend development (Naeem)
- Tasks: all pages on mocks.
- Depends on: M1 only (mocks). Output: working UI in mock mode.
- Acceptance: whole flow walkable in mock mode; `npm run build` passes. Testing: manual checklist.

### M10 — Backend integration (Jayed)
- Tasks: real endpoints, services calling `policy_engine`.
- Depends on: M6, M7, M8. Output: live API.
- Acceptance: every endpoint validates against contracts. Testing: `tests/test_api.py`.

### M11 — Administrator review and JSON export (Granthali, Jayed, Naeem)
- Tasks: approval state, exporter, review and export pages.
- Depends on: M8, M9, M10. Output: approved-only export.
- Acceptance: unapproved rules cannot be exported; export of zero approved rules is refused (409). Testing: security tests.

### M12 — Complete integration testing and demonstration (Shweta, all)
- Tasks: end-to-end test, demo script, final documentation, honest results.
- Depends on: all. Output: demo.
- Acceptance: upload to approved export runs on the sample dataset with seed 42; all tests pass. Testing: `tests/test_integration.py`.

## Progress

| Milestone | Status | Notes |
|---|---|---|
| M1 | ✅ complete | Scaffold, branches, CI, governance scripts, CODEOWNERS, contracts |
| M2 | 🔄 in progress | seed_hospital dataset created (12 users, 5 roles, 3 perms, 8 resources); Shweta's validator stub present |
| M3 | ✅ complete | `build_auth_matrix()` implemented; 288 tuples, 200 authorised on seed_hospital; decisions D-001 closed |
| M4 | ✅ complete | S+/S- sampling, stratified split, OHE encoding (fit on train only), deterministic with seed 42 |
| M5 | ✅ complete | DT/RF/GB trained with stratified CV; all three hit F1=1.0 on seed_hospital; models persisted via joblib |
| M6 | ✅ complete | Decision Tree permit paths extracted as ABACRule objects (support/confidence TEMPORARY until M7) |
| M7 | 🔄 pending | Granthali's policy_engine module; backend stubs clearly marked in pipeline_service.py |
| M8 | 🔄 pending | policy_engine.validate_policy; stub returns DT metrics as proxy |
| M9 | 🔄 in progress | Naeem's frontend; stub mode (BACKEND_STUBS=true) available day-1 |
| M10 | ✅ complete | All 9 REST endpoints wired, 85 tests passing, contract validated |
| M11 | 🔄 pending | Review/export works (approve → export confirmed in demo); XACML export stub until Granthali |
| M12 | 🔄 pending | Full integration test with Shweta's API tests; demo runs end-to-end with seed 42 |
