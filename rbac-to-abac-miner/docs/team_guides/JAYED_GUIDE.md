# Development Guide — Jayed Altaf Shaikh

**Designation:** Machine Learning Engineer and Backend Lead (also technical integration owner)
**Branches:** `feature/jayed-backend`, `feature/jayed-ml-engine`
**Hardware:** Best laptop in the team. All heavy training runs on your machine only.

## 1. Primary objective

Build the Python backend that turns an uploaded RBAC dataset into a labelled training set, trains Decision Tree, Random Forest and Gradient Boosting models, extracts candidate ABAC rules from the Decision Tree, hands them to Granthali's `policy_engine` for optimisation, validation and export, and exposes everything through stable REST APIs for Naeem's frontend.

You are the integrator, not the fixer. Each member delivers a working, tested module. You do not implement the policy engine or the frontend.

## 2. Exact module ownership (OWNER)

| Path | Purpose |
|---|---|
| `backend/app/` | FastAPI app, config, CORS, router wiring |
| `backend/api/` | Route handlers |
| `backend/services/` | Orchestration between pipeline, ML and policy_engine |
| `backend/data_pipeline/` | Loading, preprocessing, Auth matrix, sampling, encoding |
| `backend/ml_engine/` | Training, CV, tuning, evaluation, rule extraction |
| `backend/models/` | Serialised models (git-ignored) |
| `backend/schemas/`, `backend/utils/`, `backend/tests/` | Helpers and tests |
| `shared/` | Contracts. RESTRICTED: all-member approval for changes |
| `docs/`, `config/` | Documentation and configuration |

Read-only for you: `frontend/`, `policy_engine/`, `data_engineering/`, `tests/` (Shweta's).

## 3. Responsibilities

1. Backend architecture (FastAPI, Pydantic v2).
2. RBAC data loader.
3. Authorisation matrix construction.
4. Positive and negative sample generation.
5. Feature engineering and encoding.
6. Train and compare Decision Tree, Random Forest, Gradient Boosting (XGBoost optional alternative for GB).
7. Cross-validation and hyperparameter tuning.
8. Extract Decision Tree permit paths as candidate rules.
9. Save trained models.
10. Backend APIs and module integration.

## 4. Tasks in implementation order

### Task 1 — Repository setup (Milestone 1)
- Create the GitHub repo, push this scaffold, create `develop`, enable branch protection (PR required, 1 approval, CI required), set real usernames in `.github/CODEOWNERS`.
- Add collaborators. Everyone clones and creates their branch from `develop`.

### Task 2 — Backend skeleton (Milestone 1/3)
- `backend/app/main.py` with `/health`, CORS from env `FRONTEND_ORIGIN`, router includes.
- `backend/requirements.txt` (see section 9).
- Stub endpoints that return the files in `shared/sample_responses/` so Naeem and Shweta can integrate early.

### Task 3 — Loader and Auth matrix (Milestone 3)
- Load the six files (CSV or JSON), validate keys, build users x resources x permission authorisation relation using UA and PA.
- Call `data_engineering.data_validation` if available; do not duplicate its checks.

### Task 4 — Positive/negative samples (Milestone 4)
- S+ = all authorised tuples. S- = sampled unauthorised tuples with the configured ratio and seed.
- Join user and resource attributes; label column `authorised` (1/0).
- Stratified train/test split. The test split is untouched until final evaluation.
- Fit encoders on training data only. Handle class imbalance (class weights or imbalanced-learn on train only).

### Task 5 — Model training (Milestone 5)
- Train DT, RF, GB with fixed seed; stratified k-fold CV on the training split; optional grid or random search for hyperparameters inside CV.
- Report precision, recall, F1, training time on the held-out test split.
- Set `is_rule_extraction_model=True` only for the Decision Tree. Check `f1_target_met`.

### Task 6 — Rule extraction (Milestone 6)
- Walk the fitted Decision Tree; every root-to-leaf path predicting "permit" becomes an `ABACRule` (status `candidate`).
- Decode thresholds and one-hot/ordinal features back to attribute conditions with `user.` / `resource.` prefixes.
- Compute support and confidence for each rule on the training samples (reuse `policy_engine` functions once available; until then keep a private helper marked temporary).
- Filter by `min_support` and `min_confidence` from the request.

### Task 7 — Policy engine integration (Milestones 7, 8, 11)
- Services call `policy_engine.optimise_policy`, `validate_policy`, `export_policy`. Pass the full access matrix to validation.
- Never re-implement merging, pruning, WSC or export in the backend.

### Task 8 — Real endpoints (Milestone 10)
- Replace stubs one by one. Each response is built by instantiating the Pydantic model from `shared/schemas/contracts.py`.
- Enforce state rules: export is refused with HTTP 409 until at least one rule is approved.

### Task 9 — Demonstration support (Milestone 12)
- Provide a one-command demo script `scripts/run_demo.sh` or `backend/README.md` steps; document the exact seed and dataset used.

## 5. Required files and functions

```
backend/data_pipeline/loader.py          load_rbac_dataset(path_or_files, fmt) -> RBACDataset
backend/data_pipeline/preprocess.py      clean_attributes(df, config) -> df ; encode_features(train_df, test_df) -> (X_train, X_test, encoder)
backend/data_pipeline/auth_matrix.py     build_auth_matrix(dataset) -> DataFrame[user_id, resource_id, permission, authorised]
backend/data_pipeline/sampling.py        build_training_samples(auth_df, users, resources, ratio, seed) -> (samples_df, S_pos_count, S_neg_count)
backend/ml_engine/train.py               train_models(X_train, y_train, X_test, y_test, config) -> list[TrainedModelInfo]
backend/ml_engine/evaluate.py            evaluate_model(model, X, y) -> ModelMetrics
backend/ml_engine/extract_rules.py       extract_permit_rules(tree, feature_names, encoder, samples) -> list[ABACRule]
backend/services/pipeline_service.py     run_training(config) -> TrainingResponse ; get_rules(run_id) ; optimise(run_id) ; validate(policy_id) ; review(...) ; export(...)
backend/api/*.py                         routers per section 8 of PROJECT_RULES.json endpoints
backend/utils/seed.py, timing.py, storage.py
```

## 6. Input and output contracts

All request and response bodies are the Pydantic models in `shared/schemas/contracts.py`: `DatasetValidationResponse`, `RBACAuthorisationResponse`, `TrainingConfigRequest`, `TrainingResponse`, `ModelComparisonResponse`, `ExtractedRulesResponse`, `OptimisedPolicyResponse`, `PolicyValidationResponse`, `ApprovalRequest/Response`, `ExportRequest/Response`, `ErrorResponse`. Examples: `shared/sample_responses/`.

Python interface you call on Granthali's package:

```python
from policy_engine import optimise_policy, validate_policy, export_policy
```

See `docs/modules/POLICY_ENGINE.md` for exact signatures.

## 7. Dependencies

Depends on `shared/schemas`, `policy_engine` (public functions only), optionally `data_engineering.data_validation`. Others depend on your endpoints. Do not change a response structure without approval (Rule R6).

## 8. Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

## 9. Commands

```bash
uvicorn backend.app.main:app --reload --port 8000
python -m pytest backend/tests -q
python scripts/validate_governance.py
```

`backend/requirements.txt` (create it): `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `python-multipart`, `pandas`, `numpy`, `scikit-learn`, `xgboost`, `imbalanced-learn`, `shap`, `matplotlib`, `seaborn`, `graphviz`, `joblib`, `pytest`, `httpx`.

## 10. Testing instructions

- Unit tests for each function with tiny datasets (use `data_engineering/sample_datasets/`).
- Test that the split is stratified and leak-free (encoder fitted on train only).
- Test determinism: same seed gives identical metrics.
- Test that extracted rules, evaluated by `policy_engine`, reproduce the tree's positive predictions on training data.
- Contract tests: every endpoint response validates against its Pydantic model.

## 11. Integration instructions

1. Publish stub endpoints first (day 1-2) so the frontend and API tests can start.
2. Agree the `policy_engine` call signatures with Granthali before coding Task 7.
3. Open PRs into `develop`; Shweta's API tests must pass before merging integration PRs.
4. Another member reviews your own PRs.

## 12. Restrictions

- Do not implement merging, generalisation, pruning, WSC, export or the frontend.
- Rules come only from the Decision Tree.
- No GPU libraries; no new dependencies without approval.
- Do not commit model binaries.
- Never evaluate the final policy on sampled negatives alone.

## 13. Completion criteria

- All endpoints in `PROJECT_RULES.json` work and match contracts.
- Full demo flow runs from upload to approved export on the sample dataset with seed 42.
- Backend tests and Shweta's API/integration tests pass.
- `backend/README.md` and `docs/modules/{DATA_PIPELINE,ML_ENGINE,API}.md` are accurate.

## 14. Common mistakes to avoid

- Fitting encoders or imputers on all data before splitting (leakage).
- Tuning hyperparameters on the test split.
- Reporting policy metrics on the sampled dataset instead of the full matrix.
- Extracting rules from the Random Forest.
- Changing a response field "just for convenience".
- Becoming the bottleneck: publish stubs early, and make others fix their own modules.
