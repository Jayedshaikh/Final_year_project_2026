"""Orchestration service: ties together data pipeline, ML engine, and policy engine.

This is the only place where all layers are integrated. API handlers call
functions here and receive contract-valid response objects.

Policy engine calls (optimise_policy, validate_policy, export_policy) are
stubbed until Granthali's package is available. The stubs are clearly marked.
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from backend.data_pipeline.auth_matrix import build_auth_matrix, get_authorisation_roles
from backend.data_pipeline.loader import load_rbac_dataset
from backend.data_pipeline.preprocess import clean_attributes, encode_features
from backend.data_pipeline.sampling import build_training_samples, stratified_split
from backend.ml_engine.extract_rules import extract_permit_rules
from backend.ml_engine.train import load_model, train_models
from backend.services import state_store
from shared.schemas.contracts import (
    ABACRule,
    ApprovalRequest,
    ApprovalResponse,
    AuthorisationTuple,
    DatasetSummary,
    DatasetUploadRequest,
    DatasetValidationResponse,
    ExportRequest,
    ExportResponse,
    ExtractedRulesResponse,
    ModelComparisonResponse,
    ModelComparisonRow,
    OptimisedPolicyResponse,
    OptimisationSummary,
    PolicyMetrics,
    PolicyValidationResponse,
    RBACAuthorisationResponse,
    RuleDecision,
    RuleStatus,
    TrainingConfigRequest,
    TrainingResponse,
    ValidationIssue,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Policy engine integration stubs
# (Replace with real imports once Granthali's package is installed)
# --------------------------------------------------------------------------- #

def _try_import_policy_engine():
    """Attempt to import the real policy_engine package and verify it has the expected functions.

    Returns:
        The policy_engine module if all required public functions are present, else None.
    """
    try:
        import policy_engine  # noqa: F401
        # Verify the required public interface exists before trusting the module
        if (
            hasattr(policy_engine, "optimise_policy")
            and hasattr(policy_engine, "validate_policy")
            and hasattr(policy_engine, "export_policy")
        ):
            return policy_engine
        return None
    except ImportError:
        return None


# --------------------------------------------------------------------------- #
# 1. Dataset upload and validation
# --------------------------------------------------------------------------- #

def upload_dataset(
    request: DatasetUploadRequest,
    files: Dict[str, bytes],
) -> DatasetValidationResponse:
    """Load, validate, and store an uploaded RBAC dataset.

    Args:
        request: DatasetUploadRequest with metadata (name, format, attribute cols).
        files: Mapping from table name to raw file bytes.

    Returns:
        DatasetValidationResponse with status, dataset_id, summary, and issues.
    """
    issues: List[ValidationIssue] = []

    # --- Try to call Shweta's data_validation if available ---
    try:
        from data_engineering.data_validation import validate_dataset  # type: ignore
        validation_issues = validate_dataset(files, request.file_format)
        issues.extend(validation_issues)
    except ImportError:
        logger.debug("data_engineering.data_validation not available; skipping pre-checks.")
    except Exception as exc:
        logger.warning("data_engineering.data_validation raised: %s", exc)

    # --- Load the dataset ---
    try:
        dataset = load_rbac_dataset(
            files=files,
            fmt=request.file_format,
            dataset_name=request.dataset_name,
            user_attribute_columns=request.user_attribute_columns,
            resource_attribute_columns=request.resource_attribute_columns,
        )
    except ValueError as exc:
        issues.append(ValidationIssue(
            severity="error",
            code="LOAD_FAILED",
            file="upload",
            message=str(exc),
        ))
        return DatasetValidationResponse(status="invalid", dataset_id=None, summary=None, issues=issues)

    # Check for structural errors
    error_issues = [i for i in issues if i.severity == "error"]
    if error_issues:
        return DatasetValidationResponse(status="invalid", dataset_id=None, summary=None, issues=issues)

    # --- Assign dataset_id and persist ---
    dataset_id = state_store.next_dataset_id()

    # Build auth matrix for storage (needed by other endpoints)
    try:
        auth_matrix = build_auth_matrix(dataset)
    except ValueError as exc:
        issues.append(ValidationIssue(
            severity="error",
            code="AUTH_MATRIX_FAILED",
            file="upload",
            message=str(exc),
        ))
        return DatasetValidationResponse(status="invalid", dataset_id=None, summary=None, issues=issues)

    # Persist dataset tables as JSON-serialisable records
    state_store.store_dataset(dataset_id, {
        "dataset_id": dataset_id,
        "dataset_name": request.dataset_name,
        "file_format": request.file_format,
        "user_attribute_columns": dataset.user_attribute_columns,
        "resource_attribute_columns": dataset.resource_attribute_columns,
        "users": dataset.users.to_dict(orient="records"),
        "roles": dataset.roles.to_dict(orient="records"),
        "permissions": dataset.permissions.to_dict(orient="records"),
        "user_roles": dataset.user_roles.to_dict(orient="records"),
        "role_permissions": dataset.role_permissions.to_dict(orient="records"),
        "resources": dataset.resources.to_dict(orient="records"),
        "auth_matrix": auth_matrix.to_dict(orient="records"),
    })

    summary = DatasetSummary(
        n_users=len(dataset.users),
        n_roles=len(dataset.roles),
        n_permissions=len(dataset.permissions),
        n_resources=len(dataset.resources),
        n_user_roles=len(dataset.user_roles),
        n_role_permissions=len(dataset.role_permissions),
        user_attributes=dataset.user_attribute_columns,
        resource_attributes=dataset.resource_attribute_columns,
    )

    return DatasetValidationResponse(
        status="ok",
        dataset_id=dataset_id,
        summary=summary,
        issues=issues,
    )


# --------------------------------------------------------------------------- #
# 2. RBAC authorisation matrix
# --------------------------------------------------------------------------- #

def get_authorisation_response(dataset_id: str) -> RBACAuthorisationResponse:
    """Build the authorisation summary response for a dataset.

    Args:
        dataset_id: Dataset identifier.

    Returns:
        RBACAuthorisationResponse.

    Raises:
        KeyError: If dataset_id is not found (API converts to 404).
    """
    meta = state_store.get_dataset(dataset_id)
    if meta is None:
        raise KeyError(f"Dataset '{dataset_id}' not found.")

    auth_matrix = pd.DataFrame(meta["auth_matrix"])
    total = len(auth_matrix)
    n_auth = int(auth_matrix["authorised"].sum())
    n_unauth = total - n_auth
    density = n_auth / total if total > 0 else 0.0

    # Build sample tuples (first 50 authorised)
    auth_rows = auth_matrix[auth_matrix["authorised"] == 1].head(50)

    # Reconstruct dataset for roles-granting lookup
    dataset = _reconstruct_dataset(meta)

    sample_tuples = []
    for _, row in auth_rows.iterrows():
        roles = get_authorisation_roles(
            dataset,
            str(row["user_id"]),
            str(row["resource_id"]),
            str(row["permission"]),
        )
        sample_tuples.append(AuthorisationTuple(
            user_id=str(row["user_id"]),
            resource_id=str(row["resource_id"]),
            permission=str(row["permission"]),
            roles_granting=roles,
        ))

    return RBACAuthorisationResponse(
        dataset_id=dataset_id,
        total_possible_tuples=total,
        n_authorised=n_auth,
        n_unauthorised=n_unauth,
        authorisation_density=density,
        sample=sample_tuples,
    )


# --------------------------------------------------------------------------- #
# 3. Training run
# --------------------------------------------------------------------------- #

def run_training(config: TrainingConfigRequest) -> TrainingResponse:
    """Execute the full training pipeline for a dataset.

    Loads dataset, builds samples, encodes, trains all requested models with CV,
    extracts rules from the Decision Tree, and stores the run.

    Args:
        config: TrainingConfigRequest.

    Returns:
        TrainingResponse.

    Raises:
        KeyError: If dataset_id is not found.
        ValueError: On data preparation errors.
    """
    meta = state_store.get_dataset(config.dataset_id)
    if meta is None:
        raise KeyError(f"Dataset '{config.dataset_id}' not found.")

    dataset = _reconstruct_dataset(meta)
    auth_matrix = pd.DataFrame(meta["auth_matrix"])

    # Build and preprocess samples
    samples_raw, n_pos, n_neg = build_training_samples(
        auth_df=auth_matrix,
        users=dataset.users,
        resources=dataset.resources,
        user_attribute_columns=dataset.user_attribute_columns,
        resource_attribute_columns=dataset.resource_attribute_columns,
        ratio=config.negative_sampling.ratio,
        seed=config.random_seed,
        strategy=config.negative_sampling.strategy,
    )

    # Stratified split
    train_df, test_df = stratified_split(
        samples_df=samples_raw,
        test_size=config.test_size,
        seed=config.random_seed,
    )

    # Determine feature columns (all except ids and label)
    feature_cols = [
        c for c in train_df.columns
        if c not in {"user_id", "resource_id", "authorised"}
    ]

    # Clean attributes
    train_df = clean_attributes(train_df)
    test_df = clean_attributes(test_df)

    # Encode (fit on train only)
    X_train, X_test, encoder = encode_features(
        train_df=train_df,
        test_df=test_df,
        feature_columns=feature_cols,
    )

    y_train = train_df["authorised"].values
    y_test = test_df["authorised"].values

    # Train models
    trained_models = train_models(X_train, y_train, X_test, y_test, config)

    # Extract rules from Decision Tree
    dt_info = next((m for m in trained_models if m.model_name == "decision_tree"), None)
    rules: List[ABACRule] = []
    if dt_info and "decision_tree" in config.models:
        try:
            dt_model = load_model(dt_info.model_id)
            rules = extract_permit_rules(
                tree=dt_model,
                feature_names=encoder.feature_names,
                encoder=encoder,
                samples=train_df,
                min_support=config.min_support,
                min_confidence=config.min_confidence,
            )
        except Exception as exc:
            logger.warning("Rule extraction failed: %s", exc)

    # Store run
    run_id = state_store.next_run_id()
    f1_dt = dt_info.metrics.f1 if dt_info else 0.0
    f1_target_met = f1_dt >= config.f1_target

    run_data = {
        "run_id": run_id,
        "dataset_id": config.dataset_id,
        "random_seed": config.random_seed,
        "n_positive": n_pos,
        "n_negative": n_neg,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "f1_target_met": f1_target_met,
        "models": [m.model_dump() for m in trained_models],
        "rules": [r.model_dump() for r in rules],
        "feature_names": encoder.feature_names,
        "config": config.model_dump(),
        # Store the auth matrix reference for validation
        "auth_matrix": meta["auth_matrix"],
        "user_attribute_columns": dataset.user_attribute_columns,
        "resource_attribute_columns": dataset.resource_attribute_columns,
    }
    state_store.store_run(run_id, run_data)

    from shared.schemas.contracts import TrainedModelInfo
    return TrainingResponse(
        run_id=run_id,
        dataset_id=config.dataset_id,
        random_seed=config.random_seed,
        n_positive=n_pos,
        n_negative=n_neg,
        n_train=len(train_df),
        n_test=len(test_df),
        models=trained_models,
        f1_target_met=f1_target_met,
    )


# --------------------------------------------------------------------------- #
# 4. Model comparison
# --------------------------------------------------------------------------- #

def get_model_comparison(run_id: str) -> ModelComparisonResponse:
    """Return a comparison table of all trained models for a run.

    Args:
        run_id: Run identifier.

    Returns:
        ModelComparisonResponse.

    Raises:
        KeyError: If run_id is not found.
    """
    run = state_store.get_run(run_id)
    if run is None:
        raise KeyError(f"Run '{run_id}' not found.")

    rows = []
    for m in run["models"]:
        metrics = m["metrics"]
        rows.append(ModelComparisonRow(
            model_name=m["model_name"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            training_time_seconds=metrics["training_time_seconds"],
            interpretable=(m["model_name"] == "decision_tree"),
        ))

    return ModelComparisonResponse(
        run_id=run_id,
        rows=rows,
        selected_for_extraction="decision_tree",
        selection_reason=(
            "Decision Tree is the only interpretable model per the project algorithm; "
            "Random Forest and Gradient Boosting serve as accuracy references only."
        ),
    )


# --------------------------------------------------------------------------- #
# 5. Extracted rules
# --------------------------------------------------------------------------- #

def get_extracted_rules(run_id: str) -> ExtractedRulesResponse:
    """Return the candidate ABAC rules extracted from the Decision Tree.

    Args:
        run_id: Run identifier.

    Returns:
        ExtractedRulesResponse.

    Raises:
        KeyError: If run_id is not found.
    """
    run = state_store.get_run(run_id)
    if run is None:
        raise KeyError(f"Run '{run_id}' not found.")

    rules = [ABACRule(**r) for r in run.get("rules", [])]
    return ExtractedRulesResponse(
        run_id=run_id,
        n_rules=len(rules),
        rules=rules,
    )


# --------------------------------------------------------------------------- #
# 6. Policy optimisation
# --------------------------------------------------------------------------- #

def optimise_policy(run_id: str) -> OptimisedPolicyResponse:
    """Call policy_engine.optimise_policy on the extracted rules.

    If policy_engine is not yet available, returns a pass-through response
    (rules unchanged, counts zeroed) marked clearly as a stub.

    Args:
        run_id: Run identifier.

    Returns:
        OptimisedPolicyResponse.

    Raises:
        KeyError: If run_id is not found.
        ValueError: If no rules exist for optimisation.
    """
    run = state_store.get_run(run_id)
    if run is None:
        raise KeyError(f"Run '{run_id}' not found.")

    rules = [ABACRule(**r) for r in run.get("rules", [])]
    if not rules:
        raise ValueError(f"No extracted rules found for run '{run_id}'. Run training first.")

    policy_engine = _try_import_policy_engine()

    if policy_engine is not None:
        # --- Real call ---
        import pandas as pd
        samples_df = _build_decoded_samples(run)
        from policy_engine import optimise_policy as pe_optimise  # type: ignore
        from policy_engine.schemas.config import OptimisationConfig  # type: ignore

        opt_config = OptimisationConfig(
            min_support=run["config"].get("min_support", 0.01),
            min_confidence=run["config"].get("min_confidence", 0.9),
            random_seed=run["config"].get("random_seed", 42),
        )
        optimised_rules, opt_summary = pe_optimise(rules, samples_df, opt_config)

        # Validate on full access matrix
        auth_matrix_df = pd.DataFrame(run["auth_matrix"])
        dataset_meta = state_store.get_dataset(run["dataset_id"])
        dataset = _reconstruct_dataset(dataset_meta)
        user_attrs_df = dataset.users
        resource_attrs_df = dataset.resources

        from policy_engine import validate_policy as pe_validate  # type: ignore
        metrics, over_priv, under_priv = pe_validate(
            optimised_rules, auth_matrix_df, user_attrs_df, resource_attrs_df
        )
    else:
        # --- Stub: pass-through until Granthali's module is ready ---
        logger.warning("policy_engine not available; using stub optimise_policy.")
        optimised_rules = [
            r.model_copy(update={"status": RuleStatus.OPTIMISED}) for r in rules
        ]
        opt_summary = OptimisationSummary(
            rules_before=len(rules),
            rules_after=len(optimised_rules),
            n_merged=0,
            n_generalised=0,
            n_pruned_redundant=0,
            wsc_before=float(len(rules)),
            wsc_after=float(len(optimised_rules)),
        )
        metrics = _stub_policy_metrics(optimised_rules, run)

    # Assign policy_id and persist
    policy_id = state_store.next_policy_id()
    policy_data = {
        "policy_id": policy_id,
        "run_id": run_id,
        "rules": [r.model_dump() for r in optimised_rules],
        "metrics": metrics.model_dump(),
        "optimisation": opt_summary.model_dump(),
    }
    state_store.store_policy(policy_id, policy_data)

    return OptimisedPolicyResponse(
        run_id=run_id,
        policy_id=policy_id,
        rules=optimised_rules,
        optimisation=opt_summary,
        metrics=metrics,
    )


# --------------------------------------------------------------------------- #
# 7. Policy validation
# --------------------------------------------------------------------------- #

def validate_policy(policy_id: str) -> PolicyValidationResponse:
    """Re-validate the current rule set (including edits) on the full access matrix.

    Args:
        policy_id: Policy identifier.

    Returns:
        PolicyValidationResponse.

    Raises:
        KeyError: If policy_id is not found.
    """
    policy = state_store.get_policy(policy_id)
    if policy is None:
        raise KeyError(f"Policy '{policy_id}' not found.")

    rules = [ABACRule(**r) for r in policy.get("rules", [])]
    run = state_store.get_run(policy["run_id"])

    policy_engine = _try_import_policy_engine()

    if policy_engine is not None:
        auth_matrix_df = pd.DataFrame(run["auth_matrix"])
        dataset_meta = state_store.get_dataset(run["dataset_id"])
        dataset = _reconstruct_dataset(dataset_meta)
        from policy_engine import validate_policy as pe_validate  # type: ignore
        metrics, over_priv, under_priv = pe_validate(
            rules, auth_matrix_df, dataset.users, dataset.resources
        )
    else:
        logger.warning("policy_engine not available; using stub validate_policy.")
        metrics = _stub_policy_metrics(rules, run)
        over_priv = []
        under_priv = []

    # Persist updated metrics
    policy["metrics"] = metrics.model_dump()
    state_store.store_policy(policy_id, policy)

    return PolicyValidationResponse(
        policy_id=policy_id,
        metrics=metrics,
        over_privileged_examples=over_priv,
        under_privileged_examples=under_priv,
        fail_safe_default="deny",
    )


# --------------------------------------------------------------------------- #
# 8. Administrator review
# --------------------------------------------------------------------------- #

def review_policy(policy_id: str, request: ApprovalRequest) -> ApprovalResponse:
    """Apply approve / reject / edit decisions to policy rules.

    Nothing is auto-approved (Rule 14). Every transition is explicit.

    Args:
        policy_id: Policy identifier.
        request: ApprovalRequest with reviewer and list of decisions.

    Returns:
        ApprovalResponse with counts.

    Raises:
        KeyError: If policy_id is not found or a rule_id is unknown.
    """
    policy = state_store.get_policy(policy_id)
    if policy is None:
        raise KeyError(f"Policy '{policy_id}' not found.")

    rules_by_id = {r["rule_id"]: r for r in policy.get("rules", [])}

    for decision in request.decisions:
        rule_data = rules_by_id.get(decision.rule_id)
        if rule_data is None:
            raise KeyError(f"Rule '{decision.rule_id}' not found in policy '{policy_id}'.")

        if decision.decision == "approve":
            rule_data["status"] = RuleStatus.APPROVED.value
        elif decision.decision == "reject":
            rule_data["status"] = RuleStatus.REJECTED.value
        elif decision.decision == "edit":
            if decision.edited_conditions is None:
                raise ValueError(
                    f"Rule '{decision.rule_id}': 'edit' decision requires edited_conditions."
                )
            rule_data["conditions"] = [c.model_dump() for c in decision.edited_conditions]
            rule_data["status"] = RuleStatus.EDITED.value
        rule_data.setdefault("reviews", []).append({
            "reviewer": request.reviewer,
            "decision": decision.decision,
            "comment": decision.comment,
        })

    policy["rules"] = list(rules_by_id.values())
    state_store.store_policy(policy_id, policy)

    statuses = [r["status"] for r in policy["rules"]]
    n_approved = statuses.count(RuleStatus.APPROVED.value)
    n_rejected = statuses.count(RuleStatus.REJECTED.value)
    n_edited = statuses.count(RuleStatus.EDITED.value)
    n_unreviewed = sum(
        1 for s in statuses
        if s in (RuleStatus.CANDIDATE.value, RuleStatus.OPTIMISED.value)
    )

    return ApprovalResponse(
        policy_id=policy_id,
        n_approved=n_approved,
        n_rejected=n_rejected,
        n_edited_pending_revalidation=n_edited,
        n_still_unreviewed=n_unreviewed,
    )


# --------------------------------------------------------------------------- #
# 9. Policy export
# --------------------------------------------------------------------------- #

def export_policy(policy_id: str, request: ExportRequest) -> ExportResponse:
    """Export approved rules as JSON or XACML-style policy.

    Only rules with status == 'approved' are exported.
    If no rules are approved, raises ValueError (API converts to HTTP 409).

    Args:
        policy_id: Policy identifier.
        request: ExportRequest specifying the format.

    Returns:
        ExportResponse with serialised policy content.

    Raises:
        KeyError: If policy_id is not found.
        ValueError: If no approved rules exist (HTTP 409).
    """
    policy = state_store.get_policy(policy_id)
    if policy is None:
        raise KeyError(f"Policy '{policy_id}' not found.")

    policy_engine = _try_import_policy_engine()

    if policy_engine is not None:
        rules = [ABACRule(**r) for r in policy.get("rules", [])]
        from policy_engine import export_policy as pe_export  # type: ignore
        content = pe_export(rules, fmt=request.format, policy_id=policy_id)
        approved_rules = [r for r in rules if r.status == RuleStatus.APPROVED]
    else:
        logger.warning("policy_engine not available; using stub export_policy.")
        approved_rules = [
            ABACRule(**r) for r in policy.get("rules", [])
            if r["status"] == RuleStatus.APPROVED.value
        ]
        if not approved_rules:
            raise ValueError("No approved rules to export. Approve at least one rule first.")

        content = _stub_export(approved_rules, request.format, policy_id)

    if not approved_rules:
        raise ValueError("No approved rules to export. Approve at least one rule first.")

    return ExportResponse(
        policy_id=policy_id,
        format=request.format,
        n_rules_exported=len(approved_rules),
        default_decision="deny",
        content=content,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )


# --------------------------------------------------------------------------- #
# Private helpers
# --------------------------------------------------------------------------- #

def _reconstruct_dataset(meta: Dict[str, Any]):
    """Reconstruct an RBACDataset from stored metadata dicts.

    Args:
        meta: Dataset metadata as stored by store_dataset().

    Returns:
        RBACDataset with DataFrames restored from records.
    """
    from backend.data_pipeline.loader import RBACDataset
    return RBACDataset(
        users=pd.DataFrame(meta["users"]),
        roles=pd.DataFrame(meta["roles"]),
        permissions=pd.DataFrame(meta["permissions"]),
        user_roles=pd.DataFrame(meta["user_roles"]),
        role_permissions=pd.DataFrame(meta["role_permissions"]),
        resources=pd.DataFrame(meta["resources"]),
        user_attribute_columns=meta.get("user_attribute_columns", []),
        resource_attribute_columns=meta.get("resource_attribute_columns", []),
        dataset_name=meta.get("dataset_name", ""),
        file_format=meta.get("file_format", "csv"),
    )


def _build_decoded_samples(run: Dict[str, Any]) -> pd.DataFrame:
    """Build a decoded samples DataFrame from run data for policy_engine calls.

    Args:
        run: Run data dict from the state store.

    Returns:
        DataFrame with user/resource attributes and authorised label.
    """
    # We stored auth_matrix in the run; reconstruct it
    auth_matrix = pd.DataFrame(run["auth_matrix"])
    dataset_meta = state_store.get_dataset(run["dataset_id"])
    if dataset_meta is None:
        return auth_matrix
    dataset = _reconstruct_dataset(dataset_meta)

    user_attrs = dataset.user_attribute_columns
    resource_attrs = dataset.resource_attribute_columns

    # Join attributes
    users_renamed = dataset.users.rename(columns={c: f"user.{c}" for c in user_attrs})
    resources_renamed = dataset.resources.rename(columns={c: f"resource.{c}" for c in resource_attrs})

    df = auth_matrix.merge(users_renamed, on="user_id", how="left")
    df = df.merge(resources_renamed, on="resource_id", how="left")

    # Apply the same normalisation that was applied during training (lowercase categoricals)
    # so rule conditions (lowercased OHE values) match sample values.
    from backend.data_pipeline.preprocess import clean_attributes
    df = clean_attributes(df)

    return df


def _stub_policy_metrics(rules: List[ABACRule], run: Dict[str, Any]) -> PolicyMetrics:
    """Compute stub policy metrics from the auth matrix without policy_engine.

    Counts how many rules exist and returns placeholder precision/recall/F1.
    These numbers come from the Decision Tree's test metrics (first approximation).

    Args:
        rules: Current rule list (all statuses).
        run: Run data dict.

    Returns:
        PolicyMetrics stub.
    """
    auth_matrix = pd.DataFrame(run["auth_matrix"])
    n_tuples = len(auth_matrix)

    # Take DT metrics as approximate policy metrics
    dt_model_data = next(
        (m for m in run.get("models", []) if m["model_name"] == "decision_tree"), None
    )
    if dt_model_data:
        precision = dt_model_data["metrics"]["precision"]
        recall = dt_model_data["metrics"]["recall"]
        f1 = dt_model_data["metrics"]["f1"]
    else:
        precision = recall = f1 = 0.0

    active_rules = [
        r for r in rules
        if (r.status if isinstance(r.status, str) else r.status.value)
        in (RuleStatus.CANDIDATE.value, RuleStatus.OPTIMISED.value,
            RuleStatus.APPROVED.value, RuleStatus.EDITED.value)
    ]

    wsc = float(sum(1 + len(r.conditions) for r in active_rules))

    return PolicyMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        over_privilege_rate=1.0 - precision if precision > 0 else 0.0,
        under_privilege_rate=1.0 - recall if recall > 0 else 0.0,
        rule_count=len(active_rules),
        wsc=wsc,
        evaluated_on="full_access_matrix",
        n_tuples_evaluated=n_tuples,
    )


def _stub_export(rules: List[ABACRule], fmt: str, policy_id: str) -> str:
    """Produce a stub JSON or XACML export without policy_engine.

    Args:
        rules: Approved rules only.
        fmt: "json" or "xacml".
        policy_id: Policy identifier.

    Returns:
        Serialised policy string.
    """
    if fmt == "json":
        policy_doc = {
            "policy_id": policy_id,
            "default_decision": "deny",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "effect": r.effect,
                    "action": r.action,
                    "conditions": [c.model_dump() for c in r.conditions],
                    "support": r.support,
                    "confidence": r.confidence,
                }
                for r in rules
            ],
        }
        return json.dumps(policy_doc, indent=2, default=str)

    # XACML-style stub
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<Policy PolicyId="{policy_id}" RuleCombiningAlgId="permit-overrides">',
    ]
    for rule in rules:
        lines.append(f'  <Rule RuleId="{rule.rule_id}" Effect="Permit">')
        lines.append(f'    <Target><Actions><Action>{rule.action}</Action></Actions></Target>')
        lines.append("    <Condition>")
        for cond in rule.conditions:
            lines.append(
                f'      <Apply><AttributeValue attribute="{cond.attribute}" '
                f'operator="{cond.operator.value}" value="{cond.value}"/></Apply>'
            )
        lines.append("    </Condition>")
        lines.append("  </Rule>")
    lines.append('  <Rule RuleId="default-deny" Effect="Deny"/>')
    lines.append("</Policy>")
    return "\n".join(lines)
