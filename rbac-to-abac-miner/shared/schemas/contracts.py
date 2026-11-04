"""Shared Pydantic contracts for the RBAC-to-ABAC miner.

CONTRACT VERSION: 1.0.0
Owner: Project lead (Jayed) -- changes require approval of ALL four members (see PROJECT_RULES.json).

Every backend response, every frontend mock (shared/sample_responses/*.json) and every
policy_engine input/output MUST conform to these models. Do not add, remove or rename
fields without a contract change request (docs/development_rules/CHANGE_REQUEST_TEMPLATE.md).

Requires: pydantic>=2.0
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# Common
# --------------------------------------------------------------------------- #
class ErrorResponse(BaseModel):
    """Returned with a non-2xx status for every endpoint."""

    status: Literal["error"] = "error"
    code: str = Field(..., description="Machine code, e.g. VALIDATION_FAILED, DATASET_NOT_FOUND")
    message: str
    details: Optional[Dict[str, Any]] = None


class Operator(str, Enum):
    EQ = "=="
    NEQ = "!="
    IN = "in"
    NOT_IN = "not_in"
    LTE = "<="
    GT = ">"
    GTE = ">="
    LT = "<"


class RuleStatus(str, Enum):
    CANDIDATE = "candidate"   # freshly extracted, not reviewed
    OPTIMISED = "optimised"   # survived merge/generalise/prune, not reviewed
    APPROVED = "approved"     # explicit administrator action only (Rule 14)
    REJECTED = "rejected"
    EDITED = "edited"         # edited by admin, needs re-validation, not exportable until approved


# --------------------------------------------------------------------------- #
# 1. Dataset upload request / 2. Dataset validation response
# --------------------------------------------------------------------------- #
class DatasetUploadRequest(BaseModel):
    """multipart/form-data in HTTP; this model describes the metadata part.

    Files: users, roles, permissions, user_roles, role_permissions, resources.
    Format: csv or json (all files must use the same format).
    """

    dataset_name: str = Field(..., min_length=1, max_length=100)
    file_format: Literal["csv", "json"] = "csv"
    user_attribute_columns: Optional[List[str]] = Field(
        None, description="If omitted, all non-id columns of users file are used"
    )
    resource_attribute_columns: Optional[List[str]] = None


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str  # e.g. MISSING_VALUE, DUPLICATE_RECORD, DANGLING_REFERENCE
    file: str
    row: Optional[int] = None
    column: Optional[str] = None
    message: str


class DatasetSummary(BaseModel):
    n_users: int
    n_roles: int
    n_permissions: int
    n_resources: int
    n_user_roles: int
    n_role_permissions: int
    user_attributes: List[str]
    resource_attributes: List[str]


class DatasetValidationResponse(BaseModel):
    status: Literal["ok", "invalid"]
    dataset_id: Optional[str] = None  # null when status == invalid
    summary: Optional[DatasetSummary] = None
    issues: List[ValidationIssue] = []


# --------------------------------------------------------------------------- #
# 3. RBAC authorisation response
# --------------------------------------------------------------------------- #
class AuthorisationTuple(BaseModel):
    user_id: str
    resource_id: str
    permission: str  # action, e.g. "read"
    roles_granting: List[str] = []


class RBACAuthorisationResponse(BaseModel):
    status: Literal["ok"] = "ok"
    dataset_id: str
    total_possible_tuples: int
    n_authorised: int
    n_unauthorised: int
    authorisation_density: float = Field(..., ge=0, le=1)
    sample: List[AuthorisationTuple] = Field(
        default=[], description="First N authorised tuples for preview only (N<=50)"
    )


# --------------------------------------------------------------------------- #
# 4. Training configuration request / 5. Model training response
# --------------------------------------------------------------------------- #
class NegativeSamplingConfig(BaseModel):
    strategy: Literal["random", "stratified"] = "random"
    ratio: float = Field(1.0, gt=0, description="negatives per positive")


class ModelHyperparams(BaseModel):
    max_depth: Optional[int] = Field(None, ge=1)
    min_samples_leaf: Optional[int] = Field(None, ge=1)
    n_estimators: Optional[int] = Field(None, ge=1)  # RF / GB
    learning_rate: Optional[float] = Field(None, gt=0)  # GB


class TrainingConfigRequest(BaseModel):
    dataset_id: str
    models: List[Literal["decision_tree", "random_forest", "gradient_boosting"]] = [
        "decision_tree",
        "random_forest",
        "gradient_boosting",
    ]
    test_size: float = Field(0.2, gt=0, lt=1)
    cv_folds: int = Field(5, ge=2, le=10)
    random_seed: int = 42
    negative_sampling: NegativeSamplingConfig = NegativeSamplingConfig()
    tune_hyperparameters: bool = False
    hyperparams: Dict[str, ModelHyperparams] = {}
    f1_target: float = Field(0.95, ge=0, le=1)
    min_support: float = Field(0.01, ge=0, le=1)
    min_confidence: float = Field(0.9, ge=0, le=1)


class ModelMetrics(BaseModel):
    precision: float = Field(..., ge=0, le=1)
    recall: float = Field(..., ge=0, le=1)
    f1: float = Field(..., ge=0, le=1)
    accuracy: Optional[float] = Field(None, ge=0, le=1)
    cv_f1_mean: Optional[float] = None
    cv_f1_std: Optional[float] = None
    training_time_seconds: float = Field(..., ge=0)


class TrainedModelInfo(BaseModel):
    model_name: Literal["decision_tree", "random_forest", "gradient_boosting"]
    model_id: str
    metrics: ModelMetrics
    hyperparams_used: Dict[str, Any] = {}
    is_rule_extraction_model: bool = False  # only decision_tree may be True (Algorithm constraint)


class TrainingResponse(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    dataset_id: str
    random_seed: int
    n_positive: int
    n_negative: int
    n_train: int
    n_test: int
    models: List[TrainedModelInfo]
    f1_target_met: bool


# --------------------------------------------------------------------------- #
# 6. Model comparison response
# --------------------------------------------------------------------------- #
class ModelComparisonRow(BaseModel):
    model_name: str
    precision: float
    recall: float
    f1: float
    training_time_seconds: float
    interpretable: bool


class ModelComparisonResponse(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    rows: List[ModelComparisonRow]
    selected_for_extraction: Literal["decision_tree"] = "decision_tree"
    selection_reason: str


# --------------------------------------------------------------------------- #
# 7. Extracted ABAC rule
# --------------------------------------------------------------------------- #
class Condition(BaseModel):
    attribute: str = Field(..., description="Prefixed: user.<attr> or resource.<attr>")
    operator: Operator
    value: Union[str, int, float, bool, List[Union[str, int, float]]]


class ABACRule(BaseModel):
    rule_id: str
    effect: Literal["permit"] = "permit"  # deny-rule mining is OUT OF SCOPE
    action: str
    conditions: List[Condition] = Field(..., min_length=1)
    support: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    n_covered_positive: int = 0
    n_covered_negative: int = 0
    status: RuleStatus = RuleStatus.CANDIDATE
    source: Literal["tree_path", "merged", "generalised", "edited"] = "tree_path"
    derived_from: List[str] = []  # parent rule_ids when merged


class ExtractedRulesResponse(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    n_rules: int
    rules: List[ABACRule]


# --------------------------------------------------------------------------- #
# 8. Optimised policy response / 9. Policy validation response
# --------------------------------------------------------------------------- #
class PolicyMetrics(BaseModel):
    """Always computed on the FULL access matrix (never only sampled negatives)."""

    precision: float = Field(..., ge=0, le=1)
    recall: float = Field(..., ge=0, le=1)
    f1: float = Field(..., ge=0, le=1)
    over_privilege_rate: float = Field(..., ge=0, le=1)   # OPR
    under_privilege_rate: float = Field(..., ge=0, le=1)  # UPR
    rule_count: int = Field(..., ge=0)
    wsc: float = Field(..., ge=0, description="Weighted Structural Complexity")
    evaluated_on: Literal["full_access_matrix"] = "full_access_matrix"
    n_tuples_evaluated: int


class OptimisationSummary(BaseModel):
    rules_before: int
    rules_after: int
    n_merged: int
    n_generalised: int
    n_pruned_redundant: int
    wsc_before: float
    wsc_after: float


class OptimisedPolicyResponse(BaseModel):
    status: Literal["ok"] = "ok"
    run_id: str
    policy_id: str
    rules: List[ABACRule]
    optimisation: OptimisationSummary
    metrics: PolicyMetrics


class PolicyValidationResponse(BaseModel):
    status: Literal["ok"] = "ok"
    policy_id: str
    metrics: PolicyMetrics
    over_privileged_examples: List[AuthorisationTuple] = []   # permitted by ABAC, not by RBAC
    under_privileged_examples: List[AuthorisationTuple] = []  # permitted by RBAC, not by ABAC
    fail_safe_default: Literal["deny"] = "deny"


# --------------------------------------------------------------------------- #
# 10. Administrator approval request / 11. JSON export response
# --------------------------------------------------------------------------- #
class RuleDecision(BaseModel):
    rule_id: str
    decision: Literal["approve", "reject", "edit"]
    edited_conditions: Optional[List[Condition]] = None  # required when decision == "edit"
    comment: Optional[str] = None


class ApprovalRequest(BaseModel):
    policy_id: str
    reviewer: str = Field(..., min_length=1)
    decisions: List[RuleDecision] = Field(..., min_length=1)


class ApprovalResponse(BaseModel):
    status: Literal["ok"] = "ok"
    policy_id: str
    n_approved: int
    n_rejected: int
    n_edited_pending_revalidation: int
    n_still_unreviewed: int


class ExportRequest(BaseModel):
    policy_id: str
    format: Literal["json", "xacml"] = "json"


class ExportResponse(BaseModel):
    status: Literal["ok"] = "ok"
    policy_id: str
    format: Literal["json", "xacml"]
    n_rules_exported: int  # approved rules ONLY (Rule 15)
    default_decision: Literal["deny"] = "deny"
    content: str  # serialised policy document
    generated_at: str  # ISO-8601 UTC


# --------------------------------------------------------------------------- #
# Python interface between Jayed (extraction) and Granthali (policy_engine)
# --------------------------------------------------------------------------- #
# Jayed calls:  policy_engine.optimise(rules, positives_df, negatives_df, config) -> OptimisedPolicyResponse-like
# See docs/modules/POLICY_ENGINE.md section "Integration interface".
