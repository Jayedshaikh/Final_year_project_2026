# Module: ML Engine

**Owner:** Jayed (`backend/ml_engine/`, `backend/models/`). Covers report layer 4 and the extraction half of layer 5.
**Related:** `docs/modules/DATA_PIPELINE.md`, `docs/modules/POLICY_ENGINE.md`.

## Implementation status

| File | Function | Status |
|---|---|---|
| `train.py` | `train_models(X_train, y_train, X_test, y_test, config)` | ✅ Complete |
| `train.py` | `load_model(model_id)` | ✅ Complete |
| `evaluate.py` | `evaluate_model(model, X, y, ...)` | ✅ Complete |
| `extract_rules.py` | `extract_permit_rules(tree, feature_names, encoder, samples, ...)` | ✅ Complete (support/confidence TEMPORARY until policy_engine available) |

## 1. Mapping to the 22-step algorithm (Appendix B of the report)

| Step | What | Where | Owner |
|---|---|---|---|
| 1-3 | Load, clean/encode, build Auth | `data_pipeline/` | Jayed |
| 4-6 | S+, S-, combine | `data_pipeline/sampling.py` | Jayed |
| 7 | Stratified split | `data_pipeline/sampling.py` | Jayed |
| 8-10 | Train DT, RF, GB; k-fold CV; evaluate | `ml_engine/train.py`, `evaluate.py` | Jayed |
| 11-12 | Select best interpretable DT; check F1 target | `ml_engine/train.py` | Jayed |
| 13 | Extract permit paths | `ml_engine/extract_rules.py` | Jayed |
| 14-15 | Support, confidence, threshold filter | TEMPORARY helper in `extract_rules.py` (final: `policy_engine`) | Jayed → Granthali |
| 16-18 | Merge, generalise, prune | `policy_engine` | Granthali |
| 19 | Tune and pick best policy | `backend/services/` calling `policy_engine` | Jayed + Granthali |
| 20 | Validate on the full access matrix | `policy_engine.validate_policy` | Granthali |
| 21-22 | Present, export approved only | `frontend`, `policy_engine.export_policy` | Naeem, Granthali |

## 2. Models

| Name in contract | Implementation | Purpose |
|---|---|---|
| `decision_tree` | `DecisionTreeClassifier(random_state=seed, class_weight="balanced")` | **The only rule-extraction model** |
| `random_forest` | `RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)` | Accuracy reference |
| `gradient_boosting` | `GradientBoostingClassifier(random_state=seed)` | Accuracy reference |

CPU only. `is_rule_extraction_model` is `True` only for the Decision Tree.

## 3. Training procedure (`train_models`)

1. For each requested model: stratified k-fold CV on the **train split only** — records `cv_f1_mean`, `cv_f1_std`.
2. If `tune_hyperparameters=True`: `GridSearchCV` inside CV on the train split. DT grid: `max_depth ∈ {3,4,5,6,8,10,None}`, `min_samples_leaf ∈ {1,2,5,10}`, `criterion ∈ {gini,entropy}`.
3. Refit on the full train split with chosen parameters. Measure `training_time_seconds` with `time.perf_counter()`.
4. Evaluate **once** on the test split: precision, recall, F1, accuracy.
5. `f1_target_met = (decision_tree.f1 >= config.f1_target)`.
6. Persist with `joblib` to `backend/models/<model_id>.joblib` (git-ignored).

**Seed-hospital result (seed=42):** DT f1=1.0, RF f1=1.0, GB f1=1.0.

The test split never influences encoder fitting, tuning, model selection or thresholds.

## 4. Rule extraction (`extract_permit_rules`)

Walks `tree.tree_` from root. Every root-to-leaf path whose leaf predicts the positive class becomes a candidate rule:

- One-hot feature `scope.attr=cat` with threshold ≈0.5: `> 0.5` → `attr == cat`, `≤ 0.5` → `attr != cat`.
- Numeric feature: `≤ t` or `> t` preserved.
- `permission` feature encoded as OHE: its `== value` condition becomes `rule.action`.
- Repeated `==` conditions on one attribute collapse to `in` set.
- `rule_id` assigned depth-first: `R001`, `R002`, ...
- `status = "candidate"`, `source = "tree_path"`.
- Support and confidence computed via **TEMPORARY** private helper (marked `# TEMPORARY`). Replace with `policy_engine` functions once Granthali's module is available.
- Filtered by `min_support` and `min_confidence` from the request.

## 5. Outputs

`TrainingResponse`, `ModelComparisonResponse` (`selected_for_extraction` is always `decision_tree`), `ExtractedRulesResponse`. Metrics are measured values — never hardcoded.

## 6. Tests (`backend/tests/test_ml_engine.py`)

- Same seed → identical metrics and identical rules. ✅
- `is_rule_extraction_model` True for exactly DT, False for RF and GB. ✅
- CV stats (`cv_f1_mean`, `cv_f1_std`) populated after training. ✅
- Model persisted to disk and reloads (via `tmp_path` monkeypatch). ✅
- Rule IDs sequential (R001, R002, …) in depth-first order. ✅
- `min_support=1.0` filters all rules (coverage check). ✅
- `feature_names` length mismatch raises `ValueError`. ✅
- Config loader returns dict with `random_seed=42`. ✅
- Timer context manager records elapsed ≥ 0. ✅
