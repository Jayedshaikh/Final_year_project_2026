# Implementation Plan: Policy Engine Module

**Owner:** Granthali Sandesh Mahajan  
**Branch:** `feature/granthali-policy-engine`  
**Module:** `policy_engine/`  
**Dependencies:** `shared/schemas/contracts.py` (frozen), `config/mining_config.json`  
**Constraints:** NO imports from `backend/` (circular dependency forbidden), NO scikit-learn, NO FastAPI, NO ML model training, NO auto-approval, fail-safe deny-on-error everywhere.

## Overview

Implement the policy_engine module for ABAC rule optimisation, validation, WSC computation, and JSON/XACML export. Every function must use fail-safe semantics: missing attributes, type mismatches, unknown operators, malformed rules, and exceptions during evaluation return False (deny), never raise through public APIs. Default decision is deny (closed world).

## Module Structure

```
policy_engine/
├── __init__.py                  # public API: optimise_policy, validate_policy, export_policy, verify_rbac_authorisation
├── _optimise.py                 # internal: optimise_policy orchestration
├── schemas/
│   ├── __init__.py              # exports: OptimisationConfig, evaluate_condition, rule_matches, verify_rbac_authorisation, build_access_matrix, support, confidence
│   ├── config.py                # OptimisationConfig Pydantic model
│   ├── rule.py                  # evaluate_condition, rule_matches (fail-safe)
│   ├── rbac.py                  # verify_rbac_authorisation, build_access_matrix
│   └── metrics.py               # support, confidence (zero-denominator safe)
├── rule_merger/
│   ├── __init__.py              # exports: merge_rules
│   └── merger.py                # merge rules differing in one condition
├── rule_generalizer/
│   ├── __init__.py              # exports: generalise_rules
│   └── generalizer.py           # drop conditions safely
├── rule_pruner/
│   ├── __init__.py              # exports: prune_rules
│   └── pruner.py                # remove redundant/low-support rules (idempotent)
├── policy_validator/
│   ├── __init__.py              # exports: validate_policy, weighted_structural_complexity
│   ├── validator.py             # validate_policy against full matrix
│   └── wsc.py                   # weighted_structural_complexity
├── policy_exporter/
│   ├── __init__.py              # exports: export_policy
│   └── exporter.py              # export JSON and XACML-style (approved only)
├── tests/
│   ├── test_rule_evaluation.py  # evaluate_condition, rule_matches, all operators, fail-safe
│   ├── test_rbac.py             # verify_rbac_authorisation, build_access_matrix, hand example
│   ├── test_metrics.py          # support, confidence, zero-denominator
│   ├── test_merger.py           # merge rules, conflicting merge refused
│   ├── test_generalizer.py      # condition removal, confidence check
│   ├── test_pruner.py           # redundant removal, idempotence
│   ├── test_wsc.py              # WSC formula, custom weights
│   ├── test_validation.py       # validate_policy, hand-computed metrics
│   ├── test_export.py           # JSON/XACML export, unapproved rules raise ValueError
│   ├── test_public_api.py       # end-to-end integration, no backend imports
│   ├── test_security.py         # missing attribute denies, exception denies, empty policy denies
│   ├── test_edge_cases.py       # operator boundaries, zero denominators, idempotence
│   ├── test_hand_computed_validation.py  # full hand example per GRANTHALI_GUIDE section 11
│   └── test_operator_coverage.py         # all 8 operators, pass/fail/missing/type-mismatch
├── README.md                    # module docs, public API, testing commands, fail-safe semantics
└── requirements.txt             # pandas, numpy, pydantic>=2, pytest
```

## Implementation Plan

### Feature 1: Core Rule Evaluation and Schemas (FEAT-001)

**Dependencies:** None (foundation)  
**Files:** `policy_engine/schemas/config.py`, `rule.py`, `rbac.py`, `metrics.py`, `__init__.py`, tests  

- [ ] 1. Create `policy_engine/schemas/config.py` with `OptimisationConfig` Pydantic model.
      Fields: `min_support: float (ge=0, le=1)`, `min_confidence: float (ge=0, le=1)`, `confidence_tolerance: float (ge=0, le=1, default=0.0)`, `wsc_weights: dict (default {'w_rule': 1.0, 'w_cond': 1.0, 'w_val': 0.5})`, `random_seed: int (default=42)`.
      Files: `policy_engine/schemas/config.py`
      Verify: Import the model in Python REPL, instantiate with valid/invalid values, confirm Pydantic validation works.

- [ ] 2. Create `policy_engine/schemas/rule.py` with `evaluate_condition(cond: Condition, user_attrs: dict, resource_attrs: dict) -> bool`.
      Logic: Extract attribute name without prefix ('user.' or 'resource.'), look up value in appropriate dict, return False if missing/None/type mismatch, handle operators ==, !=, in, not_in, <=, <, >, >=, return False for unknown operators, wrap in try-except returning False on exception.
      Implement `rule_matches(rule: ABACRule, user_attrs: dict, resource_attrs: dict, action: str) -> bool`.
      Logic: Return False if action != rule.action or rule.conditions empty, evaluate all conditions, return True only if ALL pass, wrap in try-except returning False.
      Import ABACRule, Condition, Operator from `shared.schemas.contracts`.
      Files: `policy_engine/schemas/rule.py`
      Verify: `python -m pytest policy_engine/tests/test_rule_evaluation.py -v` — all operator tests pass, fail-safe deny on missing/error confirmed.

- [ ] 3. Create `policy_engine/schemas/rbac.py` with `verify_rbac_authorisation(ua: pd.DataFrame, pa: pd.DataFrame, user_id: str, resource_id: str, permission: str) -> bool`.
      Logic per DATA_PIPELINE.md section 2: tuple authorised iff exists role r with (user_id, r) in ua AND (r, permission) in pa where pa row's resource_id (if present and not empty) matches or is absent/empty. Return False if columns missing or user_id not found.
      Implement `build_access_matrix(users: pd.DataFrame, resources: pd.DataFrame, ua: pd.DataFrame, pa: pd.DataFrame, permissions: list[str]) -> pd.DataFrame`.
      Logic: Cartesian product users['user_id'] x resources['resource_id'] x permissions, call verify_rbac_authorisation for each, return DataFrame with columns user_id, resource_id, permission, authorised (0/1), sorted by (user_id, resource_id, permission).
      Files: `policy_engine/schemas/rbac.py`
      Verify: `python -m pytest policy_engine/tests/test_rbac.py -v` — hand-computed 3 user x 3 resource x 2 permission example (18 tuples) matches exactly.

- [ ] 4. Create `policy_engine/schemas/metrics.py` with `support(rule: ABACRule, samples: pd.DataFrame) -> float` and `confidence(rule: ABACRule, samples: pd.DataFrame) -> float`.
      Logic: support = matched_rows / total_rows. confidence = matched_positives / matched_rows. Return 0.0 if denominator == 0. Import rule_matches from .rule.
      Files: `policy_engine/schemas/metrics.py`
      Verify: `python -m pytest policy_engine/tests/test_metrics.py -v` — hand-computed 10-row example matches, zero-row input returns 0.0, rule matching nothing returns 0.0.

- [ ] 5. Update `policy_engine/schemas/__init__.py` to export: `OptimisationConfig`, `evaluate_condition`, `rule_matches`, `verify_rbac_authorisation`, `build_access_matrix`, `support`, `confidence`.
      Files: `policy_engine/schemas/__init__.py`
      Verify: `python -c "from policy_engine.schemas import OptimisationConfig, evaluate_condition, rule_matches, verify_rbac_authorisation, build_access_matrix, support, confidence; print('All imports OK')"` — no import errors.

### Feature 2: Optimisation Modules (FEAT-002)

**Dependencies:** FEAT-001 (requires schemas/metrics, schemas/config, ABACRule)  
**Files:** `policy_engine/rule_merger/merger.py`, `rule_generalizer/generalizer.py`, `rule_pruner/pruner.py`, tests  

- [ ] 6. Create `policy_engine/rule_merger/merger.py` with `merge_rules(rules: list[ABACRule], samples: pd.DataFrame, cfg: OptimisationConfig) -> tuple[list[ABACRule], int]`.
      Logic per POLICY_ENGINE.md section 4: identify pairs with same action and identical conditions except one attribute, merge == values into 'in' set or widen numeric thresholds, compute confidence on samples, accept only if >= cfg.min_confidence - cfg.confidence_tolerance, new rule gets source='merged', derived_from=[parent rule_ids], status='optimised', new rule_id like 'M001'. Return (merged_rules + surviving_originals, n_merged_count). Refuse conflicting merges.
      Files: `policy_engine/rule_merger/merger.py`, `policy_engine/rule_merger/__init__.py`
      Verify: `python -m pytest policy_engine/tests/test_merger.py -v` — merge accepted when confidence met, conflicting merge refused, derived_from/source set correctly.

- [ ] 7. Create `policy_engine/rule_generalizer/generalizer.py` with `generalise_rules(rules: list[ABACRule], samples: pd.DataFrame, cfg: OptimisationConfig) -> tuple[list[ABACRule], int]`.
      Logic per POLICY_ENGINE.md section 4: try removing one condition at a time, recompute confidence, accept removal only if confidence >= cfg.min_confidence - cfg.confidence_tolerance AND added negatives within tolerance, new rule gets source='generalised', derived_from=[original_id], status='optimised'. Return (generalised + unchanged, n_generalised_count).
      Files: `policy_engine/rule_generalizer/generalizer.py`, `policy_engine/rule_generalizer/__init__.py`
      Verify: `python -m pytest policy_engine/tests/test_generalizer.py -v` — condition removal accepted when criteria met, rejected when confidence drops, source/derived_from set.

- [ ] 8. Create `policy_engine/rule_pruner/pruner.py` with `prune_rules(rules: list[ABACRule], samples: pd.DataFrame, cfg: OptimisationConfig) -> tuple[list[ABACRule], int]`.
      Logic per POLICY_ENGINE.md section 4: drop rules with support < cfg.min_support, drop redundant rules (matched positives subset of others). Return (pruned_rules, n_pruned_count). Must be idempotent.
      Files: `policy_engine/rule_pruner/pruner.py`, `policy_engine/rule_pruner/__init__.py`
      Verify: `python -m pytest policy_engine/tests/test_pruner.py -v` — low-support dropped, redundant dropped, idempotence: prune(prune(X)) == prune(X), empty input returns empty.

### Feature 3: Validation and WSC (FEAT-003)

**Dependencies:** FEAT-001 (requires schemas/rule.rule_matches, ABACRule, PolicyMetrics)  
**Files:** `policy_engine/policy_validator/wsc.py`, `validator.py`, tests  

- [ ] 9. Create `policy_engine/policy_validator/wsc.py` with `weighted_structural_complexity(rules: list[ABACRule], weights: dict | None = None) -> float`.
      Formula per POLICY_ENGINE.md section 5: WSC = sum over rules of (w_rule + w_cond * n_conditions + w_val * total_elements_in_in/not_in_sets). Default weights: {'w_rule': 1.0, 'w_cond': 1.0, 'w_val': 0.5}. Return 0.0 for empty rules.
      Files: `policy_engine/policy_validator/wsc.py`
      Verify: `python -m pytest policy_engine/tests/test_wsc.py -v` — hand-computed WSC for 3 rules matches, empty rules returns 0.0, custom weights work.

- [ ] 10. Create `policy_engine/policy_validator/validator.py` with `validate_policy(rules: list[ABACRule], access_matrix_df: pd.DataFrame, user_attrs_df: pd.DataFrame, resource_attrs_df: pd.DataFrame, wsc_weights: dict | None = None) -> tuple[PolicyMetrics, list[AuthorisationTuple], list[AuthorisationTuple]]`.
       Logic per POLICY_ENGINE.md sections 2, 5: filter rules to counted statuses (candidate, optimised, approved, edited; reject excluded per D-010), for each tuple in access_matrix_df look up user/resource attributes, evaluate policy (ANY counted rule matches = permit, else deny), compare with RBAC authorised, compute TP, FP, FN, TN, precision, recall, F1, OPR, UPR, rule_count, wsc, collect over/under examples (limit 20 each). Handle zero denominators: precision/recall/F1/OPR/UPR = 0.0 when denominator == 0. Wrap evaluation in try-except: exception denies that tuple (fail-safe).
       Files: `policy_engine/policy_validator/validator.py`, `policy_engine/policy_validator/__init__.py`
       Verify: `python -m pytest policy_engine/tests/test_validation.py -v` — hand-computed 5 user x 3 resource x 2 permission example (30 tuples, 3 rules) metrics match exactly, rejected rules excluded, exception denies tuple.

### Feature 4: Export and Public API (FEAT-004)

**Dependencies:** FEAT-001, FEAT-002, FEAT-003 (requires all submodules to orchestrate)  
**Files:** `policy_engine/policy_exporter/exporter.py`, `_optimise.py`, `__init__.py`, tests  

- [ ] 11. Create `policy_engine/policy_exporter/exporter.py` with `export_policy(rules: list[ABACRule], fmt: str, policy_id: str) -> str`.
       Validate fmt in ['json', 'xacml'], filter rules to status=='approved' only, raise ValueError('no approved rules') if none. If fmt=='json', call _export_json (builds dict with policy_id, default_decision='deny', generated_at, rules, return json.dumps(indent=2)). If fmt=='xacml', call _export_xacml (builds XACML-style XML with Policy, per-rule Rule Effect='Permit', final Rule Effect='Deny', return ET.tostring). Per POLICY_ENGINE.md section 6.
       Files: `policy_engine/policy_exporter/exporter.py`, `policy_engine/policy_exporter/__init__.py`
       Verify: `python -m pytest policy_engine/tests/test_export.py -v` — JSON export valid and parses, XACML export valid and parses, no approved rules raises ValueError, rejected rules excluded, invalid fmt raises.

- [ ] 12. Create `policy_engine/_optimise.py` with `optimise_policy(rules: list[ABACRule], samples_df: pd.DataFrame, config: OptimisationConfig) -> tuple[list[ABACRule], OptimisationSummary]`.
       Orchestration per POLICY_ENGINE.md section 4: (1) compute wsc_before, rules_before, (2) filter below min_support/min_confidence, (3) merge_rules, (4) generalise_rules, (5) prune_rules, (6) compute wsc_after, rules_after, (7) build OptimisationSummary, return (rules, summary).
       Files: `policy_engine/_optimise.py`
       Verify: Call optimise_policy with 20 candidate rules, verify returns OptimisationSummary with counts and optimised rules list.

- [ ] 13. Update `policy_engine/__init__.py` to import and export: `optimise_policy` from ._optimise, `validate_policy` from .policy_validator, `export_policy` from .policy_exporter, `verify_rbac_authorisation` from .schemas.rbac. Add module docstring. Confirm no imports from backend/.
       Files: `policy_engine/__init__.py`
       Verify: `python -m pytest policy_engine/tests/test_public_api.py -v` — end-to-end scenario (optimise, validate, export) works, no backend imports detected, all functions return expected types.

### Feature 5: Comprehensive Tests and Documentation (FEAT-005)

**Dependencies:** FEAT-001, FEAT-002, FEAT-003, FEAT-004 (tests entire module)  
**Files:** `policy_engine/tests/*.py`, `README.md`  

- [ ] 14. Create `policy_engine/tests/test_security.py`.
       Tests: missing attribute denies, malformed rule (empty conditions) denies, exception during evaluation denies, unknown operator denies, empty policy denies all tuples, unapproved rules never exported (raise ValueError), conflicting merge refused.
       Files: `policy_engine/tests/test_security.py`
       Verify: `python -m pytest policy_engine/tests/test_security.py -v` — all security tests pass.

- [ ] 15. Create `policy_engine/tests/test_edge_cases.py`.
       Tests: support/confidence with zero-row samples returns 0.0, rule matching nothing returns 0.0, validate_policy zero-denominator handling (precision/recall/OPR/UPR when TP+FP or TP+FN or FP+TN == 0), WSC empty rules returns 0.0, prune idempotence, operator boundary values (<=, <, >, >= at exact threshold).
       Files: `policy_engine/tests/test_edge_cases.py`
       Verify: `python -m pytest policy_engine/tests/test_edge_cases.py -v` — all edge-case tests pass.

- [ ] 16. Create `policy_engine/tests/test_hand_computed_validation.py`.
       Hand-computed validation example per GRANTHALI_GUIDE.md section 11: 3 users (Alice, Bob, Charlie), 3 resources, 2 permissions, 18 tuples, manually compute RBAC authorisation, define 2 ABAC rules, manually evaluate each tuple, compute TP, FP, FN, TN, precision, recall, F1, OPR, UPR. Record reasoning in comments. Verify validate_policy returns exact values.
       Files: `policy_engine/tests/test_hand_computed_validation.py`
       Verify: `python -m pytest policy_engine/tests/test_hand_computed_validation.py -v` — hand-computed example reproduces exactly.

- [ ] 17. Create `policy_engine/tests/test_operator_coverage.py`.
       For each Operator (==, !=, in, not_in, <=, <, >, >=), test: valid pass, valid fail, missing attribute denies, type mismatch denies. 100% operator coverage.
       Files: `policy_engine/tests/test_operator_coverage.py`
       Verify: `python -m pytest policy_engine/tests/test_operator_coverage.py -v` — all 8 operators covered.

- [ ] 18. Run all policy_engine tests together.
       Verify: `python -m pytest policy_engine/tests -v` — all tests pass, no import errors, no crashes.

- [ ] 19. Update `policy_engine/README.md`.
       Document: module structure, public API functions (optimise_policy, validate_policy, export_policy, verify_rbac_authorisation), testing commands (pytest policy_engine/tests -q), edge cases handled, fail-safe deny-on-error semantics, reference to POLICY_ENGINE.md for detailed specifications. Include 'Getting Started' section with minimal example. State dependencies: pandas, numpy, pydantic>=2, pytest (no scikit-learn, no FastAPI).
       Files: `policy_engine/README.md`
       Verify: Read the README and confirm completeness.

- [ ] 20. Run governance validation.
       Verify: `python scripts/validate_governance.py` — policy_engine module ownership and contracts validate.

## Git Workflow

1. Ensure on branch `feature/granthali-policy-engine`: `git checkout feature/granthali-policy-engine` (create if not exists: `git checkout -b feature/granthali-policy-engine`).
2. After each feature (FEAT-001 through FEAT-005), commit: `git add policy_engine/` and `git commit -m "feat(policy_engine): <description>"`.
3. After all features complete and tests pass, push: `git push -u origin feature/granthali-policy-engine`.
4. Do NOT push to main. Create a pull request into `develop` for review.

## Exact Signatures (Public API)

```python
# policy_engine/__init__.py
def optimise_policy(
    rules: list[ABACRule],
    samples_df: pd.DataFrame,
    config: OptimisationConfig
) -> tuple[list[ABACRule], OptimisationSummary]:
    """Optimise ABAC rules via filter, merge, generalise, prune. Returns optimised rules and summary."""
    ...

def validate_policy(
    rules: list[ABACRule],
    access_matrix_df: pd.DataFrame,
    user_attrs_df: pd.DataFrame,
    resource_attrs_df: pd.DataFrame,
    wsc_weights: dict | None = None
) -> tuple[PolicyMetrics, list[AuthorisationTuple], list[AuthorisationTuple]]:
    """Validate policy against full RBAC access matrix. Returns metrics, over-examples, under-examples."""
    ...

def export_policy(rules: list[ABACRule], fmt: str, policy_id: str) -> str:
    """Export approved rules as JSON or XACML-style XML. Raises ValueError if no approved rules."""
    ...

def verify_rbac_authorisation(
    ua: pd.DataFrame,
    pa: pd.DataFrame,
    user_id: str,
    resource_id: str,
    permission: str
) -> bool:
    """Verify if tuple is RBAC-authorised per DATA_PIPELINE.md section 2."""
    ...
```

## Fail-Safe Rules (Critical)

1. **Missing attributes, null values, type mismatches** → `evaluate_condition` returns `False` (deny).
2. **Unknown operators** → `evaluate_condition` returns `False` (deny).
3. **Malformed rules (empty conditions)** → `rule_matches` returns `False` (deny).
4. **Any exception during evaluation** → catch and return `False` (deny), log error, never raise through public API.
5. **Default decision** → `deny` (closed world): policy permits only if ANY counted rule matches, else deny.
6. **Zero denominators** → precision, recall, F1, OPR, UPR return `0.0` when denominator is 0.
7. **Counted rules for validation** → status in `(candidate, optimised, approved, edited)`; `rejected` excluded (D-010).
8. **Export** → uses `status == approved` only; raises `ValueError` if none approved.
9. **Optimisation acceptance** → merge/generalise accepted only if confidence >= threshold - tolerance; never introduce over-privilege beyond tolerance.

## Edge-Case Notes

- **support/confidence on empty samples** → return `0.0`.
- **rule matching nothing** → support `0.0`, confidence `0.0`.
- **empty policy (no rules)** → denies all tuples: recall `0.0`, precision undefined (treat as `0.0`), UPR high if RBAC authorises some.
- **conflicting merge** → refused (different actions or contradictory conditions).
- **idempotence of pruning** → `prune(prune(X)) == prune(X)`.
- **operator boundaries** → test `<=` vs `<` at exact threshold: value=5, condition <=5 is True, <5 is False.
- **resource-scoped PA** → PA row with resource_id grants only that resource; blank/absent resource_id grants all resources.

## Testing Strategy

- **Hand-computed examples**: Every module has at least one test with hand-computed expected answer and reasoning in comments (per GRANTHALI_GUIDE.md section 10).
- **Boundary values**: Test each operator at boundaries (value == threshold, value == threshold±epsilon).
- **Zero denominators**: Test support, confidence, precision, recall, F1, OPR, UPR when denominator is 0.
- **Fail-safe**: Test missing attribute, malformed rule, exception during evaluation all deny.
- **Idempotence**: Test `prune(prune(rules)) == prune(rules)`.
- **Security**: Test unapproved rules never exported, empty policy denies all, conflicting merge refused.
- **Integration**: Test end-to-end: optimise → validate → export with small scenario (10 rules, 50 tuples).

## Verification Commands

```bash
# Individual feature tests
python -m pytest policy_engine/tests/test_rule_evaluation.py -v
python -m pytest policy_engine/tests/test_rbac.py -v
python -m pytest policy_engine/tests/test_metrics.py -v
python -m pytest policy_engine/tests/test_merger.py -v
python -m pytest policy_engine/tests/test_generalizer.py -v
python -m pytest policy_engine/tests/test_pruner.py -v
python -m pytest policy_engine/tests/test_wsc.py -v
python -m pytest policy_engine/tests/test_validation.py -v
python -m pytest policy_engine/tests/test_export.py -v
python -m pytest policy_engine/tests/test_public_api.py -v
python -m pytest policy_engine/tests/test_security.py -v
python -m pytest policy_engine/tests/test_edge_cases.py -v
python -m pytest policy_engine/tests/test_hand_computed_validation.py -v
python -m pytest policy_engine/tests/test_operator_coverage.py -v

# All tests
python -m pytest policy_engine/tests -v

# Governance validation
python scripts/validate_governance.py
```

## Dependencies

Install from repository root:
```bash
pip install pandas numpy "pydantic>=2" pytest
```

Do NOT install: scikit-learn, fastapi, uvicorn (not needed for policy_engine).

## Completion Checklist

- [ ] All 20 plan items completed
- [ ] All public functions implemented with docstrings and type hints
- [ ] Hand-computed validation example reproduces exactly
- [ ] All tests pass: `python -m pytest policy_engine/tests -v`
- [ ] Governance validation passes: `python scripts/validate_governance.py`
- [ ] No imports from `backend/` (circular dependency check)
- [ ] All fail-safe rules verified in tests
- [ ] README.md complete and accurate
- [ ] Committed to `feature/granthali-policy-engine` branch
- [ ] Pushed to remote (NOT to main)
- [ ] Pull request created into `develop` for review

---

**Notes:**
- This plan is the fallback if FEAT workflow is not used. If FEAT artifacts exist under `.agents/tasks/task-granthali-policy-engine/`, they take precedence and decompose the work into 5 features (FEAT-001 through FEAT-005) implemented sequentially.
- Every step must leave the codebase in a buildable, testable state.
- Granthali works on low-spec laptop, so no ML training, no large datasets, only small CSV/JSON files.
- Jayed calls `policy_engine` functions from `backend/services/`; dependency direction is `backend → policy_engine → shared`, never the reverse.
