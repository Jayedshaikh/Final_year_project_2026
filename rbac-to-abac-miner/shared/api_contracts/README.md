# API contracts index

Authoritative: `shared/schemas/contracts.py`. Endpoint list: `PROJECT_RULES.json -> api_standards.endpoints`. Narrative: `docs/modules/API.md`. Field tables with examples: `docs/modules/DATA_CONTRACTS.md` (generated).

| # | Contract | Endpoint | Request model | Response model | Sample |
|---|---|---|---|---|---|
| 1 | Dataset upload request | POST `/api/v1/datasets/upload` | `DatasetUploadRequest` + files | (see 2) | inline in DATA_CONTRACTS.md |
| 2 | Dataset validation response | same | | `DatasetValidationResponse` | `dataset_validation_ok.json`, `dataset_validation_invalid.json` |
| 3 | RBAC authorisation response | GET `/datasets/{dataset_id}/authorisation` | | `RBACAuthorisationResponse` | `rbac_authorisation.json` |
| 4 | Training configuration request | POST `/training/run` | `TrainingConfigRequest` | (see 5) | `training_request.json` |
| 5 | Model training response | same | | `TrainingResponse` | `training_response.json` |
| 6 | Model comparison response | GET `/training/{run_id}/comparison` | | `ModelComparisonResponse` | `model_comparison.json` |
| 7 | Extracted ABAC rule | GET `/training/{run_id}/rules` | | `ExtractedRulesResponse` (`ABACRule` list) | `extracted_rules.json` |
| 8 | Optimised policy response | POST `/policies/optimise/{run_id}` | | `OptimisedPolicyResponse` | `optimised_policy.json` |
| 9 | Policy validation response | GET `/policies/{policy_id}/validation` | | `PolicyValidationResponse` | `policy_validation.json` |
| 10 | Administrator approval request | POST `/policies/{policy_id}/review` | `ApprovalRequest` | `ApprovalResponse` | `approval_request.json`, `approval_response.json` |
| 11 | JSON export response | POST `/policies/{policy_id}/export` | `ExportRequest` | `ExportResponse` | `export_request.json`, `export_response.json` |
| - | Error (all endpoints) | any non-2xx | | `ErrorResponse` | `error_response.json` |

All paths are under `/api/v1`. Every contract has: field names, types, required/optional (tables in DATA_CONTRACTS.md), an example request or response (samples), and the shared error shape.
