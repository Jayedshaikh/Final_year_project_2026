# Policy Engine Module

**Owner:** Granthali Sandesh Mahajan  
**Module:** `policy_engine/`  
**Branch:** `feature/granthali-policy-engine`

## Overview

The Policy Engine module handles everything that happens to ABAC rules AFTER they are extracted from the Decision Tree:

1. **Rule Evaluation** - Evaluate ABAC rules against user/resource attributes
2. **RBAC Verification** - Verify authorization according to RBAC model
3. **Metrics Computation** - Calculate support and confidence
4. **Rule Optimization** - Merge, generalize, and prune rules
5. **Policy Validation** - Validate against full RBAC access matrix
6. **WSC Computation** - Calculate Weighted Structural Complexity
7. **Policy Export** - Export to JSON and XACML-style XML formats

## Architecture

```
policy_engine/
├── __init__.py                  # Public API
├── schemas/                     # Core schemas and evaluation
│   ├── config.py               # OptimisationConfig
│   ├── rule.py                 # evaluate_condition, rule_matches
│   ├── rbac.py                 # RBAC verification
│   └── metrics.py              # support, confidence
├── rule_merger/                 # Merge similar rules
├── rule_generalizer/            # Remove conditions safely
├── rule_pruner/                 # Remove redundant rules
├── policy_validator/            # Full matrix validation
│   ├── validator.py            # validate_policy
│   └── wsc.py                  # Weighted Structural Complexity
├── policy_exporter/             # JSON and XACML export
└── tests/                       # Comprehensive test suite
```

## Public API

### `optimise_policy`

Optimize ABAC policy through filtering, merging, generalization, and pruning.

```python
from policy_engine import optimise_policy, OptimisationConfig

rules, summary = optimise_policy(
    rules=candidate_rules,
    samples_df=samples_df,
    config=OptimisationConfig(
        min_support=0.01,
        min_confidence=0.8,
        confidence_tolerance=0.0,
        wsc_weights={"w_rule": 1.0, "w_cond": 1.0, "w_val": 0.5},
    )
)
```

**Pipeline:** Filter → Merge → Generalize → Prune

### `validate_policy`

Validate ABAC policy against full RBAC access matrix.

```python
from policy_engine import validate_policy

metrics, over_privileged, under_privileged = validate_policy(
    rules=rules,
    access_matrix_df=access_matrix_df,
    user_attrs_df=user_attrs_df,
    resource_attrs_df=resource_attrs_df,
)
```

**Returns:**
- `PolicyMetrics`: precision, recall, F1, OPR, UPR, rule_count, WSC
- `over_privileged`: List of FP tuples (permitted by policy, not by RBAC)
- `under_privileged`: List of FN tuples (permitted by RBAC, not by policy)

### `export_policy`

Export approved rules to JSON or XACML-style XML.

```python
from policy_engine import export_policy

# JSON format
json_policy = export_policy(rules, fmt="json", policy_id="policy_001")

# XACML-style XML
xml_policy = export_policy(rules, fmt="xacml", policy_id="policy_001")
```

**Security:** Only exports approved rules. Raises `ValueError` if no approved rules exist.

### `verify_rbac_authorisation`

Verify if a tuple is authorized according to RBAC model.

```python
from policy_engine import verify_rbac_authorisation

is_authorized = verify_rbac_authorisation(
    ua=user_assignment_df,
    pa=permission_assignment_df,
    user_id="u123",
    resource_id="r456",
    permission="read",
)
```

## Installation

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# Install dependencies
pip install pandas numpy "pydantic>=2" pytest
```

## Dependencies

- **pandas** - Data manipulation
- **numpy** - Numerical operations
- **pydantic>=2** - Data validation
- **pytest** - Testing

**NOT included:** scikit-learn, FastAPI (by design - policy engine is ML-free)

## Testing

Run all tests:

```bash
python -m pytest policy_engine/tests -v
```

Run specific test modules:

```bash
# Rule evaluation tests
python -m pytest policy_engine/tests/test_rule_evaluation.py -v

# Validation tests
python -m pytest policy_engine/tests/test_validation_simple.py -v

# Export tests
python -m pytest policy_engine/tests/test_export_simple.py -v
```

## Security and Fail-Safe Behavior

The policy engine follows **fail-safe deny-on-error** semantics throughout:

- **Missing attributes** → deny (False)
- **Type mismatches** → deny (False)
- **Unknown operators** → deny (False)
- **Exceptions during evaluation** → deny (False)
- **Default decision** → deny (closed world)
- **Never auto-approve** rules
- **Never export unapproved** rules

## Key Design Constraints

1. **NO imports from `backend/`** - Avoids circular dependencies
2. **NO scikit-learn** - Policy engine is ML-free
3. **NO FastAPI** - Backend integration only
4. **Fail-safe everywhere** - Errors always result in deny
5. **Evidence-based optimization** - Never introduce over-privilege beyond tolerance

## Integration with Backend

The backend (`backend/services/`) calls the policy engine's public API:

```python
# In backend/services/policy_service.py
from policy_engine import optimise_policy, validate_policy, export_policy

# Optimize rules
optimized_rules, summary = optimise_policy(rules, samples, config)

# Validate policy
metrics, over_priv, under_priv = validate_policy(
    optimized_rules, access_matrix, user_attrs, resource_attrs
)

# Export approved rules
json_policy = export_policy(optimized_rules, "json", policy_id)
```

## Data Contracts

All contracts are imported from `shared/schemas/contracts.py`:

- `ABACRule` - ABAC rule structure
- `Condition` - Rule condition (attribute, operator, value)
- `PolicyMetrics` - Validation metrics
- `OptimisationSummary` - Optimization results
- `AuthorisationTuple` - User-resource-permission tuple
- `RuleStatus` - Rule status (candidate, optimised, approved, rejected, edited)

## Metrics Definitions

### Support and Confidence

- **Support** = rows matched by rule / total rows
- **Confidence** = positives matched / rows matched

### Validation Metrics

- **TP** (True Positive): Permitted by both policy and RBAC
- **FP** (False Positive): Permitted by policy, NOT by RBAC (over-privileged)
- **FN** (False Negative): Permitted by RBAC, NOT by policy (under-privileged)
- **TN** (True Negative): Denied by both

- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1** = 2 * precision * recall / (precision + recall)
- **OPR** (Over-Privilege Rate) = FP / (FP + TN)
- **UPR** (Under-Privilege Rate) = FN / (TP + FN)

### WSC (Weighted Structural Complexity)

```
WSC = Σ (w_rule + w_cond * n_conditions + w_val * total_in_set_elements)
```

Default weights: `w_rule=1.0, w_cond=1.0, w_val=0.5`

## Export Formats

### JSON Format

```json
{
  "policy_id": "policy_001",
  "default_decision": "deny",
  "generated_at": "2026-11-04T10:30:00Z",
  "rules": [
    {
      "rule_id": "R001",
      "effect": "permit",
      "action": "read",
      "conditions": [
        {
          "attribute": "user.dept",
          "operator": "==",
          "value": "IT"
        }
      ],
      "support": 0.8,
      "confidence": 0.9
    }
  ]
}
```

### XACML-Style XML

XACML-style representation with permit-overrides combining algorithm, one `<Rule Effect="Permit">` per approved rule, and a default deny rule.

**Note:** This is a readable XACML-style representation, not a certified XACML 3.0 implementation.

## Completion Status

- ✅ Rule evaluation (evaluate_condition, rule_matches)
- ✅ RBAC verification (verify_rbac_authorisation, build_access_matrix)
- ✅ Metrics (support, confidence)
- ✅ Rule merger (merge similar rules)
- ✅ Rule generalizer (remove conditions safely)
- ✅ Rule pruner (remove redundant rules)
- ✅ Policy validator (full matrix validation)
- ✅ WSC calculator (Weighted Structural Complexity)
- ✅ Policy exporter (JSON + XACML-style XML)
- ✅ Public API (optimise_policy, validate_policy, export_policy)
- ✅ Comprehensive tests (79 tests passing)
- ✅ Documentation complete

## Next Steps

1. **Integration Testing** - Test with backend when implemented
2. **Hand-Computed Example** - Add detailed hand-computed validation example
3. **Performance Optimization** - Profile and optimize for large datasets
4. **Additional Tests** - Edge cases and boundary conditions

## Documentation

- `docs/modules/POLICY_ENGINE.md` - Detailed module specification
- `docs/team_guides/GRANTHALI_GUIDE.md` - Implementation guide
- `shared/schemas/contracts.py` - Data contracts

## Maintainer

**Granthali Sandesh Mahajan**  
Security Logic and ABAC Policy Engineer  
Email: granthali@example.com  
Branch: `feature/granthali-policy-engine`

---

**Last Updated:** November 4, 2026  
**Status:** Implementation Complete ✅
