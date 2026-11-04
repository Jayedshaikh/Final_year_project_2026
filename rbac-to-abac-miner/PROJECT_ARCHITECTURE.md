# PROJECT_ARCHITECTURE.md

## 1. Overview

Seven logical layers (from the project specification), implemented by four owners:

| Layer | Content | Implemented in | Owner |
|---|---|---|---|
| 1 Data collection | import users, roles, permissions, UA, PA, resources, attributes | `backend/data_pipeline/loader.py` | Jayed |
| 2 Preprocessing | validate, normalise, encode | `data_engineering/data_validation` (checks), `backend/data_pipeline/preprocess.py` | Shweta, Jayed |
| 3 Training data | Auth relation, S+, S-, split | `backend/data_pipeline/` | Jayed |
| 4 Supervised learning | DT, RF, GB, CV, tuning, comparison | `backend/ml_engine/` | Jayed |
| 5 Rule extraction and optimisation | permit paths, support, confidence, merge, generalise, prune | extraction: `backend/ml_engine/extract_rules.py` (Jayed); optimisation: `policy_engine/` (Granthali) | Jayed, Granthali |
| 6 Policy validation | precision, recall, F1, OPR, UPR, rule count, WSC | `policy_engine/policy_validator/` | Granthali |
| 7 Review and export | approve, reject, edit, export JSON/XACML | UI: `frontend/`; state: `backend/services/`; export: `policy_engine/policy_exporter/` | Naeem, Jayed, Granthali |

## 2. System diagram

```
                     +-----------------------------+
                     |  frontend (React)  Naeem    |
                     +--------------+--------------+
                                    | REST JSON (contracts.py)
                     +--------------v--------------+
                     |  backend/api  (FastAPI)     |  Jayed
                     +--------------+--------------+
                                    |
                     +--------------v--------------+
                     |  backend/services           |
                     +---+----------+----------+---+
                         |          |          |
          +--------------v--+  +----v-------+  +--v-------------------+
          | data_pipeline   |  | ml_engine  |  | policy_engine        |
          | (Jayed)         |  | (Jayed)    |  | (Granthali)          |
          +--------+--------+  +------------+  +----------------------+
                   |
        data_engineering.data_validation (Shweta, library)

shared/schemas/contracts.py is imported by all of the above.
```

## 3. Data flow

1. Upload six files, validate (`DatasetValidationResponse`), assign `dataset_id`.
2. Build Auth relation: tuple (user, resource, permission) is authorised iff some role is assigned to the user (UA) and holds the permission (PA).
3. S+ = authorised tuples. S- = sampled unauthorised tuples (ratio, seed). Join attributes. Stratified split.
4. Encode (fit on train only), train models.

## 4. Model flow

Train DT, RF, GB with CV on the train split. Evaluate on the test split. Compare. The Decision Tree is the rule-extraction model; RF and GB are accuracy references. Check the configured F1 target.

## 5. Policy flow

DT permit paths become candidate `ABACRule`s with support and confidence, filtered by thresholds. `policy_engine.optimise_policy` merges, generalises and prunes. `validate_policy` evaluates against the **full** access matrix and returns `PolicyMetrics`. The administrator approves, rejects or edits. `export_policy` emits JSON or XACML-style output containing approved rules only, with default decision deny.

Rule status lifecycle: `candidate` to `optimised` to `approved` or `rejected`; `edited` after an admin edit, which must be re-validated and approved again before export.

## 6. API communication

REST over JSON under `/api/v1`. Endpoints are listed in `PROJECT_RULES.json` (`api_standards.endpoints`). The frontend can run on mocks copied from `shared/sample_responses/`.

## 7. Module dependencies

```
frontend -> (mocks) shared/sample_responses ; (live) backend/api
backend/api -> backend/services -> data_pipeline, ml_engine, policy_engine
ml_engine -> data_pipeline
policy_engine -> shared only            (must not import backend)
data_engineering -> shared only
tests -> everything (read-only use)
```

## 8. Integration sequence

1. Contracts and mocks (done in scaffold).
2. Shweta's small dataset to Jayed's loader.
3. Jayed's stub API to Naeem and Shweta.
4. Auth matrix cross-checked: Jayed, Granthali, Shweta's oracle agree.
5. Samples and training; rules extracted.
6. Granthali's functions plugged into services.
7. Frontend switches from mocks to live endpoints, page by page.
8. End-to-end test and demo.

## 9. Implementation decisions to confirm

See `docs/development_rules/DECISIONS.md`.
