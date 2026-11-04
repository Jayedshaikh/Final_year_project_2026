# config/

Owner: Jayed (RESTRICTED: other members propose changes by PR, reviewed by Jayed). JSON cannot hold comments, so every key is explained here.

`mining_config.json` is loaded once by `backend/utils/` and passed down as plain values. `policy_engine` never reads this file itself; Jayed builds its `OptimisationConfig` from it.

| Key | Meaning | Used by |
|---|---|---|
| `random_seed` | Seed for sampling, splits, CV, models. Default 42. | all of backend |
| `test_size` | Held-out test fraction. | data_pipeline |
| `cv_folds` | k for stratified k-fold CV on the train split. | ml_engine |
| `negative_sampling.strategy` / `.ratio` | `random` or `stratified`; negatives per positive. | data_pipeline |
| `f1_target` | Decision Tree test F1 that must be reached (`f1_target_met`). | ml_engine |
| `min_support`, `min_confidence` | Rule filters. | extraction, policy_engine |
| `confidence_tolerance` | How far below `min_confidence` a merge or generalisation may fall. 0.0 means none. | policy_engine |
| `preprocessing.*` | Imputation strategy (always reported) and case normalisation. | data_pipeline |
| `decision_tree_grid` | Search space used when `tune_hyperparameters` is true. | ml_engine |
| `random_forest_defaults`, `gradient_boosting_defaults` | Reference model settings. | ml_engine |
| `wsc_weights` | `WSC = sum(w_rule + w_cond * n_conditions + w_val * set_elements)`. | policy_engine |
| `mining_objective` | Score for choosing among candidate policies: `w_f1*F1 - w_opr*OPR - w_upr*UPR - w_wsc*(WSC / WSC_before_optimisation)`. Higher is better. | services (tuning loop) |
| `validation.max_examples` | Max over- and under-privileged examples returned. | policy_engine |
| `upload.*` | Upload size and extension limits. | api |

All numeric defaults are **implementation decisions** until checked against the report. Change them here only through a reviewed PR, and record the reason in `docs/development_rules/DECISIONS.md`. The request body (`TrainingConfigRequest`) overrides the file for a single run.
