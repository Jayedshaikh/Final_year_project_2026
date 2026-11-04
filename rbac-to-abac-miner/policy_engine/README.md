# policy_engine/

Owner: **Granthali**. Lightweight Python (pandas, numpy, pydantic). Never imports `backend`, scikit-learn or FastAPI.

## Public API (frozen; see `docs/modules/POLICY_ENGINE.md`)

```python
from policy_engine import optimise_policy, validate_policy, export_policy, verify_rbac_authorisation
```

## Layout

```
policy_engine/
  __init__.py            exports the four public functions
  schemas/               rule evaluation, RBAC verification, support/confidence, OptimisationConfig
  rule_merger/           merge_rules
  rule_generalizer/      generalise_rules
  rule_pruner/           prune_rules
  policy_validator/      validate_policy, WSC, mining objective
  policy_exporter/       export_policy (JSON, XACML-style)
  tests/
```

`ABACRule`, `Condition`, `PolicyMetrics`, `OptimisationSummary` come from `shared/schemas/contracts.py`; do not copy them.

## Setup and tests

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r policy_engine/requirements.txt
python -m pytest policy_engine/tests -q
```

## Security behaviour (tested)

Default decision is **deny**. Missing attribute, bad type, unknown operator, malformed rule or an exception means no permit. Only `approved` rules are exported. Nothing is auto-approved.

Guide: `docs/team_guides/GRANTHALI_GUIDE.md`. Metric definitions and the worked example: `docs/modules/VALIDATION.md`.

## Status

Scaffold only. Granthali updates this file with usage examples as each function lands.
