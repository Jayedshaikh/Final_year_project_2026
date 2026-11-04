# shared/

Owner: **Jayed** (integration owner). **Changes need approval from all four members** (RESTRICTED).

```
shared/
  schemas/            contracts.py: Pydantic v2 models, the single source of truth
  api_contracts/      README.md: contract index and change procedure
  sample_responses/   one valid JSON example per contract (also the frontend mocks)
  tests/              test_contracts.py
```

## Use

```python
from shared.schemas.contracts import ABACRule, Condition, PolicyMetrics   # run from the repo root
```

Frontend: copy `sample_responses/*.json` into `frontend/src/services/mocks/` unchanged.

## Checks

```bash
python scripts/validate_governance.py        # every sample validates against its model
python -m pytest shared/tests -q             # closed enums, permit-only, deny default, bounds
python scripts/generate_contract_docs.py     # regenerate docs/modules/DATA_CONTRACTS.md
```

## Changing a contract

Follow `docs/development_rules/CHANGE_REQUEST_TEMPLATE.md`: all four approve, bump `CONTRACT_VERSION`, update samples, regenerate `DATA_CONTRACTS.md`, update dependent code in the same PR series. Never rename or retype a field "just for convenience".
