# Data Contracts (contract version 1.0.0)

**Owner:** Jayed. **Source of truth:** `shared/schemas/contracts.py` (Pydantic v2). **Mocks:** `shared/sample_responses/`.
This file is **generated** from `contracts.py` by the script described in `shared/README.md`. Do not edit the field tables by hand; change `contracts.py` through a change request (`docs/development_rules/CHANGE_REQUEST_TEMPLATE.md`), then regenerate.

## Rules

1. Every request and response in the system is one of the models below. No ad-hoc dicts across module boundaries.
2. Required vs optional is exactly as in the tables. A field marked `no` may be omitted by the sender; receivers must tolerate its absence.
3. Frontend mocks, backend responses and `policy_engine` inputs/outputs follow the same models.
4. Any change (add, remove, rename, retype a field) needs approval of all four members, a `CONTRACT_VERSION` bump and regenerated samples.
5. Errors always use `ErrorResponse`:

```json
{
  "status": "error",
  "code": "DATASET_NOT_FOUND",
  "message": "No dataset with id ds_999",
  "details": null
}
```

6. Enumerations: rule `status` is one of `candidate, optimised, approved, rejected, edited`; `effect` is always `permit` (deny-rule mining is out of scope); condition operators are `==, !=, in, not_in, <=, >, >=, <`.
7. Attribute names in conditions are prefixed: `user.<attribute>` or `resource.<attribute>`.
8. Timestamps are ISO-8601 UTC strings.

## Dataset file formats (inputs to contract 1)

CSV: six files, header row. JSON: one object, key per table, array of records, for example:

```json
{
  "users": [{"user_id": "u1", "department": "Finance", "position": "Analyst"}],
  "roles": [{"role_id": "r_fin", "role_name": "Finance Analyst"}],
  "permissions": [{"permission_id": "read"}],
  "user_roles": [{"user_id": "u1", "role_id": "r_fin"}],
  "role_permissions": [{"role_id": "r_fin", "permission_id": "read", "resource_id": ""}],
  "resources": [{"resource_id": "res1", "sensitivity": "low", "type": "report"}]
}
```

Column rules are in `docs/modules/DATA_PIPELINE.md`.

## Contract 1: Dataset upload request

**Endpoint:** `POST /api/v1/datasets/upload`

### `DatasetUploadRequest`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `dataset_name` | `str` | yes | MinLen=1, MaxLen=100 |
| `file_format` | `one of 'csv', 'json'` | no | `'csv'` |
| `user_attribute_columns` | `Optional[List[str]]` | no | `None`; If omitted, all non-id columns of users file are used |
| `resource_attribute_columns` | `Optional[List[str]]` | no | `None` |

**Example request (metadata part of the multipart form):**

```json
{
  "dataset_name": "hospital_small",
  "file_format": "csv"
}
```

The response is contract 2.

**Error:** `ErrorResponse` (see Rules).

## Contract 2: Dataset validation response

**Endpoint:** `same call`

### `DatasetValidationResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok', 'invalid'` | yes |  |
| `dataset_id` | `Optional[str]` | no | `None` |
| `summary` | `Optional[DatasetSummary]` | no | `None` |
| `issues` | `List[ValidationIssue]` | no | `[]` |

### `ValidationIssue`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `severity` | `one of 'error', 'warning'` | yes |  |
| `code` | `str` | yes |  |
| `file` | `str` | yes |  |
| `row` | `Optional[int]` | no | `None` |
| `column` | `Optional[str]` | no | `None` |
| `message` | `str` | yes |  |

### `DatasetSummary`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `n_users` | `int` | yes |  |
| `n_roles` | `int` | yes |  |
| `n_permissions` | `int` | yes |  |
| `n_resources` | `int` | yes |  |
| `n_user_roles` | `int` | yes |  |
| `n_role_permissions` | `int` | yes |  |
| `user_attributes` | `List[str]` | yes |  |
| `resource_attributes` | `List[str]` | yes |  |

**Example response** (`shared/sample_responses/dataset_validation_ok.json`):

```json
{
  "status": "ok",
  "dataset_id": "ds_001",
  "summary": {
    "n_users": 12,
    "n_roles": 4,
    "n_permissions": 3,
    "n_resources": 8,
    "n_user_roles": 14,
    "n_role_permissions": 9,
    "user_attributes": [
      "department",
      "seniority",
      "clearance"
    ],
    "resource_attributes": [
      "department",
      "sensitivity",
      "type"
    ]
  },
  "issues": [
    {
      "severity": "warning",
      "code": "MISSING_VALUE",
      "file": "users.csv",
      "row": 7,
      "column": "clearance",
      "message": "Missing value imputed with 'unknown'"
    }
  ]
}
```

**Example response** (`shared/sample_responses/dataset_validation_invalid.json`):

```json
{
  "status": "invalid",
  "dataset_id": null,
  "summary": null,
  "issues": [
    {
      "severity": "error",
      "code": "DANGLING_REFERENCE",
      "file": "user_roles.csv",
      "row": 3,
      "column": "role_id",
      "message": "role_id 'R99' not found in roles.csv"
    }
  ]
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 3: RBAC authorisation response

**Endpoint:** `GET /api/v1/datasets/{dataset_id}/authorisation`

### `RBACAuthorisationResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `dataset_id` | `str` | yes |  |
| `total_possible_tuples` | `int` | yes |  |
| `n_authorised` | `int` | yes |  |
| `n_unauthorised` | `int` | yes |  |
| `authorisation_density` | `float` | yes | Ge=0, Le=1 |
| `sample` | `List[AuthorisationTuple]` | no | `[]`; First N authorised tuples for preview only (N<=50) |

### `AuthorisationTuple`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `user_id` | `str` | yes |  |
| `resource_id` | `str` | yes |  |
| `permission` | `str` | yes |  |
| `roles_granting` | `List[str]` | no | `[]` |

**Example response** (`shared/sample_responses/rbac_authorisation.json`):

```json
{
  "status": "ok",
  "dataset_id": "ds_001",
  "total_possible_tuples": 288,
  "n_authorised": 96,
  "n_unauthorised": 192,
  "authorisation_density": 0.3333333333333333,
  "sample": [
    {
      "user_id": "U001",
      "resource_id": "RES003",
      "permission": "read",
      "roles_granting": [
        "R_ANALYST"
      ]
    }
  ]
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 4: Training configuration request

**Endpoint:** `POST /api/v1/training/run`

### `TrainingConfigRequest`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `dataset_id` | `str` | yes |  |
| `models` | `List[one of 'decision_tree', 'random_forest', 'gradient_boosting']` | no | `['decision_tree', 'random_forest', 'gradient_boosting']` |
| `test_size` | `float` | no | `0.2`, Gt=0, Lt=1 |
| `cv_folds` | `int` | no | `5`, Ge=2, Le=10 |
| `random_seed` | `int` | no | `42` |
| `negative_sampling` | `NegativeSamplingConfig` | no | `NegativeSamplingConfig(strategy='random', ratio=1.0)` |
| `tune_hyperparameters` | `bool` | no | `False` |
| `hyperparams` | `Dict[str, ModelHyperparams]` | no | `{}` |
| `f1_target` | `float` | no | `0.95`, Ge=0, Le=1 |
| `min_support` | `float` | no | `0.01`, Ge=0, Le=1 |
| `min_confidence` | `float` | no | `0.9`, Ge=0, Le=1 |

### `NegativeSamplingConfig`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `strategy` | `one of 'random', 'stratified'` | no | `'random'` |
| `ratio` | `float` | no | `1.0`, Gt=0; negatives per positive |

### `ModelHyperparams`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `max_depth` | `Optional[int]` | no | `None`, Ge=1 |
| `min_samples_leaf` | `Optional[int]` | no | `None`, Ge=1 |
| `n_estimators` | `Optional[int]` | no | `None`, Ge=1 |
| `learning_rate` | `Optional[float]` | no | `None`, Gt=0 |

**Example request** (`shared/sample_responses/training_request.json`):

```json
{
  "dataset_id": "ds_001",
  "models": [
    "decision_tree",
    "random_forest",
    "gradient_boosting"
  ],
  "test_size": 0.2,
  "cv_folds": 5,
  "random_seed": 42,
  "negative_sampling": {
    "strategy": "random",
    "ratio": 1.0
  },
  "tune_hyperparameters": false,
  "hyperparams": {},
  "f1_target": 0.95,
  "min_support": 0.01,
  "min_confidence": 0.9
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 5: Model training response

**Endpoint:** `same call`

### `TrainingResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `run_id` | `str` | yes |  |
| `dataset_id` | `str` | yes |  |
| `random_seed` | `int` | yes |  |
| `n_positive` | `int` | yes |  |
| `n_negative` | `int` | yes |  |
| `n_train` | `int` | yes |  |
| `n_test` | `int` | yes |  |
| `models` | `List[TrainedModelInfo]` | yes |  |
| `f1_target_met` | `bool` | yes |  |

### `TrainedModelInfo`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `model_name` | `one of 'decision_tree', 'random_forest', 'gradient_boosting'` | yes |  |
| `model_id` | `str` | yes |  |
| `metrics` | `ModelMetrics` | yes |  |
| `hyperparams_used` | `Dict[str, Any]` | no | `{}` |
| `is_rule_extraction_model` | `bool` | no | `False` |

### `ModelMetrics`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `precision` | `float` | yes | Ge=0, Le=1 |
| `recall` | `float` | yes | Ge=0, Le=1 |
| `f1` | `float` | yes | Ge=0, Le=1 |
| `accuracy` | `Optional[float]` | no | `None`, Ge=0, Le=1 |
| `cv_f1_mean` | `Optional[float]` | no | `None` |
| `cv_f1_std` | `Optional[float]` | no | `None` |
| `training_time_seconds` | `float` | yes | Ge=0 |

**Example response** (`shared/sample_responses/training_response.json`):

```json
{
  "status": "ok",
  "run_id": "run_001",
  "dataset_id": "ds_001",
  "random_seed": 42,
  "n_positive": 96,
  "n_negative": 96,
  "n_train": 153,
  "n_test": 39,
  "models": [
    {
      "model_name": "decision_tree",
      "model_id": "m_dt_001",
      "metrics": {
        "precision": 0.96,
        "recall": 0.95,
        "f1": 0.955,
        "accuracy": null,
        "cv_f1_mean": 0.955,
        "cv_f1_std": 0.01,
        "training_time_seconds": 0.02
      },
      "hyperparams_used": {
        "max_depth": 6
      },
      "is_rule_extraction_model": true
    },
    {
      "model_name": "random_forest",
      "model_id": "m_rf_001",
      "metrics": {
        "precision": 0.98,
        "recall": 0.97,
        "f1": 0.975,
        "accuracy": null,
        "cv_f1_mean": 0.975,
        "cv_f1_std": 0.01,
        "training_time_seconds": 0.4
      },
      "hyperparams_used": {},
      "is_rule_extraction_model": false
    },
    {
      "model_name": "gradient_boosting",
      "model_id": "m_gb_001",
      "metrics": {
        "precision": 0.98,
        "recall": 0.98,
        "f1": 0.98,
        "accuracy": null,
        "cv_f1_mean": 0.98,
        "cv_f1_std": 0.01,
        "training_time_seconds": 0.7
      },
      "hyperparams_used": {},
      "is_rule_extraction_model": false
    }
  ],
  "f1_target_met": true
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 6: Model comparison response

**Endpoint:** `GET /api/v1/training/{run_id}/comparison`

### `ModelComparisonResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `run_id` | `str` | yes |  |
| `rows` | `List[ModelComparisonRow]` | yes |  |
| `selected_for_extraction` | `one of 'decision_tree'` | no | `'decision_tree'` |
| `selection_reason` | `str` | yes |  |

### `ModelComparisonRow`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `model_name` | `str` | yes |  |
| `precision` | `float` | yes |  |
| `recall` | `float` | yes |  |
| `f1` | `float` | yes |  |
| `training_time_seconds` | `float` | yes |  |
| `interpretable` | `bool` | yes |  |

**Example response** (`shared/sample_responses/model_comparison.json`):

```json
{
  "status": "ok",
  "run_id": "run_001",
  "rows": [
    {
      "model_name": "decision_tree",
      "precision": 0.96,
      "recall": 0.95,
      "f1": 0.955,
      "training_time_seconds": 0.02,
      "interpretable": true
    },
    {
      "model_name": "random_forest",
      "precision": 0.98,
      "recall": 0.97,
      "f1": 0.975,
      "training_time_seconds": 0.4,
      "interpretable": false
    },
    {
      "model_name": "gradient_boosting",
      "precision": 0.98,
      "recall": 0.98,
      "f1": 0.98,
      "training_time_seconds": 0.7,
      "interpretable": false
    }
  ],
  "selected_for_extraction": "decision_tree",
  "selection_reason": "Decision Tree is the only interpretable model; RF and GB serve as accuracy references."
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 7: Extracted ABAC rule

**Endpoint:** `GET /api/v1/training/{run_id}/rules`

### `ExtractedRulesResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `run_id` | `str` | yes |  |
| `n_rules` | `int` | yes |  |
| `rules` | `List[ABACRule]` | yes |  |

### `ABACRule`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `rule_id` | `str` | yes |  |
| `effect` | `one of 'permit'` | no | `'permit'` |
| `action` | `str` | yes |  |
| `conditions` | `List[Condition]` | yes | MinLen=1 |
| `support` | `float` | yes | Ge=0, Le=1 |
| `confidence` | `float` | yes | Ge=0, Le=1 |
| `n_covered_positive` | `int` | no | `0` |
| `n_covered_negative` | `int` | no | `0` |
| `status` | `one of 'candidate', 'optimised', 'approved', 'rejected', 'edited'` | no | `'candidate'` |
| `source` | `one of 'tree_path', 'merged', 'generalised', 'edited'` | no | `'tree_path'` |
| `derived_from` | `List[str]` | no | `[]` |

### `Condition`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `attribute` | `str` | yes | Prefixed: user.<attr> or resource.<attr> |
| `operator` | `one of '==', '!=', 'in', 'not_in', '<=', '>', '>=', '<'` | yes |  |
| `value` | `Union[str, int, float, bool, List[Union[str, int, float]]]` | yes |  |

**Example response** (`shared/sample_responses/extracted_rules.json`):

```json
{
  "status": "ok",
  "run_id": "run_001",
  "n_rules": 2,
  "rules": [
    {
      "rule_id": "R001",
      "effect": "permit",
      "action": "read",
      "conditions": [
        {
          "attribute": "user.department",
          "operator": "==",
          "value": "Finance"
        },
        {
          "attribute": "resource.sensitivity",
          "operator": "in",
          "value": [
            "low",
            "medium"
          ]
        }
      ],
      "support": 0.12,
      "confidence": 0.97,
      "n_covered_positive": 30,
      "n_covered_negative": 1,
      "status": "candidate",
      "source": "tree_path",
      "derived_from": []
    },
    {
      "rule_id": "R002",
      "effect": "permit",
      "action": "read",
      "conditions": [
        {
          "attribute": "user.seniority",
          "operator": ">=",
          "value": 3
        },
        {
          "attribute": "resource.type",
          "operator": "==",
          "value": "report"
        }
      ],
      "support": 0.08,
      "confidence": 0.93,
      "n_covered_positive": 20,
      "n_covered_negative": 2,
      "status": "candidate",
      "source": "tree_path",
      "derived_from": []
    }
  ]
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 8: Optimised policy response

**Endpoint:** `POST /api/v1/policies/optimise/{run_id}`

### `OptimisedPolicyResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `run_id` | `str` | yes |  |
| `policy_id` | `str` | yes |  |
| `rules` | `List[ABACRule]` | yes |  |
| `optimisation` | `OptimisationSummary` | yes |  |
| `metrics` | `PolicyMetrics` | yes |  |

### `OptimisationSummary`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `rules_before` | `int` | yes |  |
| `rules_after` | `int` | yes |  |
| `n_merged` | `int` | yes |  |
| `n_generalised` | `int` | yes |  |
| `n_pruned_redundant` | `int` | yes |  |
| `wsc_before` | `float` | yes |  |
| `wsc_after` | `float` | yes |  |

### `PolicyMetrics`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `precision` | `float` | yes | Ge=0, Le=1 |
| `recall` | `float` | yes | Ge=0, Le=1 |
| `f1` | `float` | yes | Ge=0, Le=1 |
| `over_privilege_rate` | `float` | yes | Ge=0, Le=1 |
| `under_privilege_rate` | `float` | yes | Ge=0, Le=1 |
| `rule_count` | `int` | yes | Ge=0 |
| `wsc` | `float` | yes | Ge=0; Weighted Structural Complexity |
| `evaluated_on` | `one of 'full_access_matrix'` | no | `'full_access_matrix'` |
| `n_tuples_evaluated` | `int` | yes |  |

**Example response** (`shared/sample_responses/optimised_policy.json`):

```json
{
  "status": "ok",
  "run_id": "run_001",
  "policy_id": "pol_001",
  "rules": [
    {
      "rule_id": "R001",
      "effect": "permit",
      "action": "read",
      "conditions": [
        {
          "attribute": "user.department",
          "operator": "==",
          "value": "Finance"
        },
        {
          "attribute": "resource.sensitivity",
          "operator": "in",
          "value": [
            "low",
            "medium"
          ]
        }
      ],
      "support": 0.12,
      "confidence": 0.97,
      "n_covered_positive": 30,
      "n_covered_negative": 1,
      "status": "candidate",
      "source": "tree_path",
      "derived_from": []
    },
    {
      "rule_id": "R002",
      "effect": "permit",
      "action": "read",
      "conditions": [
        {
          "attribute": "user.seniority",
          "operator": ">=",
          "value": 3
        },
        {
          "attribute": "resource.type",
          "operator": "==",
          "value": "report"
        }
      ],
      "support": 0.08,
      "confidence": 0.93,
      "n_covered_positive": 20,
      "n_covered_negative": 2,
      "status": "candidate",
      "source": "tree_path",
      "derived_from": []
    }
  ],
  "optimisation": {
    "rules_before": 5,
    "rules_after": 2,
    "n_merged": 2,
    "n_generalised": 1,
    "n_pruned_redundant": 1,
    "wsc_before": 14.0,
    "wsc_after": 7.0
  },
  "metrics": {
    "precision": 0.97,
    "recall": 0.94,
    "f1": 0.955,
    "over_privilege_rate": 0.01,
    "under_privilege_rate": 0.06,
    "rule_count": 2,
    "wsc": 7.0,
    "evaluated_on": "full_access_matrix",
    "n_tuples_evaluated": 288
  }
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 9: Policy validation response

**Endpoint:** `GET /api/v1/policies/{policy_id}/validation`

### `PolicyValidationResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `policy_id` | `str` | yes |  |
| `metrics` | `PolicyMetrics` | yes |  |
| `over_privileged_examples` | `List[AuthorisationTuple]` | no | `[]` |
| `under_privileged_examples` | `List[AuthorisationTuple]` | no | `[]` |
| `fail_safe_default` | `one of 'deny'` | no | `'deny'` |

**Example response** (`shared/sample_responses/policy_validation.json`):

```json
{
  "status": "ok",
  "policy_id": "pol_001",
  "metrics": {
    "precision": 0.97,
    "recall": 0.94,
    "f1": 0.955,
    "over_privilege_rate": 0.01,
    "under_privilege_rate": 0.06,
    "rule_count": 2,
    "wsc": 7.0,
    "evaluated_on": "full_access_matrix",
    "n_tuples_evaluated": 288
  },
  "over_privileged_examples": [
    {
      "user_id": "U009",
      "resource_id": "RES005",
      "permission": "read",
      "roles_granting": []
    }
  ],
  "under_privileged_examples": [
    {
      "user_id": "U002",
      "resource_id": "RES001",
      "permission": "read",
      "roles_granting": [
        "R_ANALYST"
      ]
    }
  ],
  "fail_safe_default": "deny"
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 10: Administrator approval request

**Endpoint:** `POST /api/v1/policies/{policy_id}/review`

### `ApprovalRequest`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `policy_id` | `str` | yes |  |
| `reviewer` | `str` | yes | MinLen=1 |
| `decisions` | `List[RuleDecision]` | yes | MinLen=1 |

### `RuleDecision`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `rule_id` | `str` | yes |  |
| `decision` | `one of 'approve', 'reject', 'edit'` | yes |  |
| `edited_conditions` | `Optional[List[Condition]]` | no | `None` |
| `comment` | `Optional[str]` | no | `None` |

### `ApprovalResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `policy_id` | `str` | yes |  |
| `n_approved` | `int` | yes |  |
| `n_rejected` | `int` | yes |  |
| `n_edited_pending_revalidation` | `int` | yes |  |
| `n_still_unreviewed` | `int` | yes |  |

**Example request** (`shared/sample_responses/approval_request.json`):

```json
{
  "policy_id": "pol_001",
  "reviewer": "admin",
  "decisions": [
    {
      "rule_id": "R001",
      "decision": "approve",
      "edited_conditions": null,
      "comment": null
    },
    {
      "rule_id": "R002",
      "decision": "reject",
      "edited_conditions": null,
      "comment": "Too broad"
    }
  ]
}
```

**Example response** (`shared/sample_responses/approval_response.json`):

```json
{
  "status": "ok",
  "policy_id": "pol_001",
  "n_approved": 1,
  "n_rejected": 1,
  "n_edited_pending_revalidation": 0,
  "n_still_unreviewed": 0
}
```

**Error:** `ErrorResponse` (see Rules).

## Contract 11: JSON export response

**Endpoint:** `POST /api/v1/policies/{policy_id}/export`

### `ExportRequest`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `policy_id` | `str` | yes |  |
| `format` | `one of 'json', 'xacml'` | no | `'json'` |

### `ExportResponse`

| Field | Type | Required | Default / constraint |
|---|---|---|---|
| `status` | `one of 'ok'` | no | `'ok'` |
| `policy_id` | `str` | yes |  |
| `format` | `one of 'json', 'xacml'` | yes |  |
| `n_rules_exported` | `int` | yes |  |
| `default_decision` | `one of 'deny'` | no | `'deny'` |
| `content` | `str` | yes |  |
| `generated_at` | `str` | yes |  |

**Example request** (`shared/sample_responses/export_request.json`):

```json
{
  "policy_id": "pol_001",
  "format": "json"
}
```

**Example response** (`shared/sample_responses/export_response.json`):

```json
{
  "status": "ok",
  "policy_id": "pol_001",
  "format": "json",
  "n_rules_exported": 1,
  "default_decision": "deny",
  "content": "{\"policy_id\": \"pol_001\", \"default_decision\": \"deny\", \"rules\": [{\"rule_id\": \"R001\", \"effect\": \"permit\", \"action\": \"read\", \"conditions\": [{\"attribute\": \"user.department\", \"operator\": \"==\", \"value\": \"Finance\"}, {\"attribute\": \"resource.sensitivity\", \"operator\": \"in\", \"value\": [\"low\", \"medium\"]}], \"support\": 0.12, \"confidence\": 0.97, \"n_covered_positive\": 30, \"n_covered_negative\": 1, \"status\": \"candidate\", \"source\": \"tree_path\", \"derived_from\": []}]}",
  "generated_at": "2026-11-03T12:00:00Z"
}
```

**Error:** `ErrorResponse` (see Rules).
