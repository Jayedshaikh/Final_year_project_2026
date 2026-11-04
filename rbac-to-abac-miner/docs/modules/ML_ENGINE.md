# Module: ML Engine

**Owner:** Jayed (`backend/ml_engine/`, `backend/models/`). Covers report layer 4 and the extraction half of layer 5.
**Related:** `docs/modules/DATA_PIPELINE.md`, `docs/modules/POLICY_ENGINE.md`.

## 1. Mapping to the 22-step algorithm (Appendix B of the report)

| Step | What | Where | Owner |
|---|---|---|---|
| 1-3 | Load, clean/encode, build Auth | `data_pipeline/` | Jayed |
| 4-6 | S+, S-, combine | `data_pipeline/sampling.py` | Jayed |
| 7 | Stratified split | `data_pipeline/sampling.py` | Jayed |
| 8-10 | Train DT, RF, GB; k-fold CV; evaluate | `ml_engine/train.py`, `evaluate.py` | Jayed |
| 11-12 | Select best interpretable DT; check F1 target | `ml_engine/train.py` | Jayed |
| 13 | Extract permit paths | `ml_engine/extract_rules.py` | Jayed |
| 14-15 | Support, confidence, threshold filter | `policy_engine` (final); temporary private helper in `extract_rules.py` | Granthali / Jayed |
| 16-18 | Merge, generalise, prune | `policy_engine` | Granthali |
| 19 | Tune and pick best policy by mining objective | orchestrated in `backend/services/`, calling `policy_engine` | Jayed + Granthali |
| 20 | Validate on the full access matrix | `policy_engine.validate_policy` | Granthali |
| 21-22 | Present, export approved only | `frontend`, `policy_engine.export_policy` | Naeem, Granthali |

The step numbering comes from the project specification. Check it against Appendix B of the report and record any difference in `DECISIONS.md`.

## 2. Models

| Name in contract | Implementation | Purpose |
|---|---|---|
| `decision_tree` | `sklearn.tree.DecisionTreeClassifier(random_state=seed, class_weight="balanced")` | **The only rule-extraction model** |
| `random_forest` | `RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=-1)` | accuracy reference |
| `gradient_boosting` | `GradientBoostingClassifier(random_state=seed)` (XGBoost optional, D-006) | accuracy reference |

CPU only, no GPU libraries. `is_rule_extraction_model` is `True` only for the Decision Tree.

## 3. Training procedure (`train_models`)

1. Input: `X_train, y_train, X_test, y_test`, `TrainingConfigRequest`.
2. For each requested model: stratified k-fold CV on the **train split only** (`cv_folds`, shuffle, `random_state = seed`) records `cv_f1_mean`, `cv_f1_std`.
3. If `tune_hyperparameters`: grid or randomised search **inside the CV on the train split**. Default Decision Tree grid: `max_depth in {3,4,5,6,8,10,None}`, `min_samples_leaf in {1,2,5,10}`, `criterion in {gini, entropy}`. Record the chosen values in `hyperparams_used`.
4. Refit on the full train split with the chosen parameters. Measure `training_time_seconds` with `time.perf_counter()` around the final fit.
5. Evaluate **once** on the test split: precision, recall, F1 (positive class = authorised), accuracy.
6. `f1_target_met = (decision_tree.f1 >= config.f1_target)`. If false, continue but report it; do not silently lower the target.
7. Persist with `joblib` to `backend/models/<model_id>.joblib` (git-ignored) together with the encoder and config.

The test split must never influence encoder fitting, tuning, model selection or thresholds.

## 4. Rule extraction (`extract_permit_rules`)

`extract_permit_rules(tree, feature_names, encoder, samples) -> list[ABACRule]`

1. Walk `tree.tree_` from the root. Keep each root-to-leaf path whose leaf predicts the positive class (`argmax(value) == 1`).
2. For each split on feature `f` with threshold `t`:
   - one-hot feature `scope.attr=cat` (threshold 0.5): `<= t` becomes `attr != cat`, `> t` becomes `attr == cat`;
   - numeric feature: `<=` / `>` with the threshold `t` as stored;
   - the `permission` feature becomes the rule's `action` (a path with several permissions is split into one rule per permission).
3. Emit conditions with prefixed names (`user.department`, `resource.sensitivity`). Combine repeated `!=` on one attribute into a `not_in` set, and `==` plus `!=` on one attribute into the `==`.
4. `rule_id` is deterministic: `R001`, `R002`, ... in depth-first order. `status = "candidate"`, `source = "tree_path"`.
5. `n_covered_positive` / `n_covered_negative` come from the leaf's training samples. `support` and `confidence` follow the definitions in `docs/modules/POLICY_ENGINE.md` section 3. Until Granthali's functions exist, use a private helper marked `# TEMPORARY`, and replace it afterwards.
6. Filter by `min_support` and `min_confidence`. Never extract from Random Forest or Gradient Boosting.

Acceptance: evaluating the extracted rule set (through `policy_engine`'s evaluator) on the training samples reproduces the tree's positive predictions for the retained paths.

## 5. Outputs

`TrainingResponse`, `ModelComparisonResponse` (`selected_for_extraction` is always `decision_tree`), `ExtractedRulesResponse`; see `docs/modules/DATA_CONTRACTS.md`. Metrics are measured values only. Hard-coded or invented numbers are forbidden outside `shared/sample_responses/`.

## 6. Tests (Jayed, `backend/tests/`)

- Same seed gives identical metrics and identical rules; different seed may differ.
- Decision Tree on a planted-pattern dataset (Shweta's `small`) recovers the planted rule.
- CV never touches the test split (assert via index sets).
- `is_rule_extraction_model` true for exactly one model.
- Rule decoding: a hand-built 3-node tree decodes to the expected conditions.
- Persisted model reloads and predicts identically.
