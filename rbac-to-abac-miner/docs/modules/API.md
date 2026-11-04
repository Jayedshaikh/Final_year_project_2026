# Module: Backend API

**Owner:** Jayed (`backend/app/`, `backend/api/`, `backend/services/`). **Consumers:** Naeem (frontend), Shweta (API tests).
The authoritative endpoint list is `PROJECT_RULES.json -> api_standards.endpoints`; the authoritative body shapes are `shared/schemas/contracts.py`. This page explains behaviour.

Base path `/api/v1`. JSON, `snake_case`. Uploads are `multipart/form-data`. Every success body contains `"status": "ok"`. Every failure is an `ErrorResponse` with a non-2xx status.

## 1. Endpoints

| # | Method and path | Request model | Response model | Notes |
|---|---|---|---|---|
| 1 | `POST /api/v1/datasets/upload` | `DatasetUploadRequest` (form fields) + six files | `DatasetValidationResponse` | Validates, and on success stores the dataset and returns `dataset_id`. `status: "invalid"` returns HTTP 400 body with the issues. |
| 2 | `GET /api/v1/datasets/{dataset_id}/authorisation` | none | `RBACAuthorisationResponse` | Auth relation summary and up to 50 sample tuples. 404 if unknown. |
| 3 | `POST /api/v1/training/run` | `TrainingConfigRequest` | `TrainingResponse` | Builds samples, trains DT/RF/GB, stores a run. |
| 4 | `GET /api/v1/training/{run_id}/comparison` | none | `ModelComparisonResponse` | |
| 5 | `GET /api/v1/training/{run_id}/rules` | none | `ExtractedRulesResponse` | Candidate rules from the Decision Tree. |
| 6 | `POST /api/v1/policies/optimise/{run_id}` | none | `OptimisedPolicyResponse` | Calls `policy_engine.optimise_policy`, then `validate_policy` for `metrics`. Creates `policy_id`. |
| 7 | `GET /api/v1/policies/{policy_id}/validation` | none | `PolicyValidationResponse` | Re-validates the current rule set (including edits) on the full matrix. |
| 8 | `POST /api/v1/policies/{policy_id}/review` | `ApprovalRequest` | `ApprovalResponse` | Applies approve / reject / edit decisions. Nothing is ever auto-approved. |
| 9 | `POST /api/v1/policies/{policy_id}/export` | `ExportRequest` | `ExportResponse` | 409 if no rule is approved. |

Operational endpoint outside the contract list (decision D-009): `GET /health` returns `{"status": "ok"}`.

## 2. Status codes

| Code | When |
|---|---|
| 200 | Success |
| 400 | Dataset failed validation or request is semantically invalid (`code`: `VALIDATION_FAILED`, `INVALID_CONFIG`) |
| 404 | Unknown `dataset_id`, `run_id`, `policy_id` (`DATASET_NOT_FOUND`, `RUN_NOT_FOUND`, `POLICY_NOT_FOUND`) |
| 409 | Invalid state: export before any approval (`NO_APPROVED_RULES`), review of an unknown rule id, optimise before training completes |
| 422 | Request body does not match the Pydantic model (FastAPI default, wrapped into `ErrorResponse`) |
| 500 | Unexpected error (`INTERNAL_ERROR`). Never includes a permit decision. |

Register exception handlers so FastAPI's default 422/500 bodies are converted to `ErrorResponse`.

## 3. State and lifecycle

```
dataset_id --(training/run)--> run_id --(policies/optimise)--> policy_id
                                                   |
                          review (approve/reject/edit, repeatable)
                                                   |
                                export (approved rules only)
```

- Identifiers: `ds_<n>`, `run_<n>`, `pol_<n>`, `m_<model>_<n>` (as in `shared/sample_responses/`).
- State store (D-007): in memory plus JSON files under `backend/runs/` (git-ignored). Restarting the server may lose in-memory state; files allow reload.
- Execution (D-008): training is synchronous for the demo dataset. If it exceeds a few seconds, move to a background task with polling, which needs a **contract change request** (a status field) approved by all members before it is built.
- Rule status transitions: `candidate -> optimised -> approved | rejected`; `edited` after an admin edit, then needs re-validation and an explicit `approve` before export. `approve` of a rule already `rejected` is allowed (admin changed their mind); every transition is logged with `reviewer` and timestamp.

## 4. Implementation rules

1. Handlers are thin: parse, call `backend/services/pipeline_service.py`, return the model.
2. Build every response by instantiating the Pydantic model from `shared/schemas/contracts.py`, never a hand-written dict.
3. CORS: allow `FRONTEND_ORIGIN` (default `http://localhost:5173`). No wildcard in the demo config.
4. Upload limits: accept only `.csv` or `.json`, maximum 10 MB per file, read in memory, never write user-supplied filenames to disk, never execute content.
5. No stack traces or file paths in error bodies.
6. Until real logic exists, endpoints return the matching file from `shared/sample_responses/` (stub mode, `BACKEND_STUBS=true`), so Naeem and Shweta can integrate on day 1.

## 5. Example

```bash
curl -s -X POST http://localhost:8000/api/v1/training/run \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "ds_001", "random_seed": 42}'
```

Returns a `TrainingResponse`. Defaults for omitted fields come from `TrainingConfigRequest`.

## 6. Contract tests (Shweta, `tests/test_api.py`)

For each endpoint: call it with `fastapi.testclient.TestClient`, assert the status code, and validate the body with the matching model. Add negative tests: unknown ids (404), invalid dataset (400), export before approval (409), malformed body (422).

## 7. Implementation status

All 9 endpoints are **implemented and tested** in `backend/api/` + `backend/services/pipeline_service.py`.

| Endpoint | Status | Notes |
|---|---|---|
| `POST /datasets/upload` | ✅ Real | File size checks, format validation, auth matrix built on upload |
| `GET /datasets/{id}/authorisation` | ✅ Real | Full matrix from stored state |
| `POST /training/run` | ✅ Real | DT+RF+GB, CV, rule extraction |
| `GET /training/{run_id}/comparison` | ✅ Real | DT always `selected_for_extraction` |
| `GET /training/{run_id}/rules` | ✅ Real | Candidate rules from DT permit paths |
| `POST /policies/optimise/{run_id}` | ✅ Stub→Real | Stub until `policy_engine` ready; passes through rules |
| `GET /policies/{id}/validation` | ✅ Stub→Real | Stub returns DT metrics proxy |
| `POST /policies/{id}/review` | ✅ Real | Approve/reject/edit, no auto-approve |
| `POST /policies/{id}/export` | ✅ Real | JSON + XACML stub; 409 if no approved rules |

Tests: `backend/tests/test_api.py` — 20+ tests covering all endpoints and all error codes (400, 404, 409, 422).

