# data_engineering/

Owner: **Shweta**. Lightweight Python (pandas, pydantic, pytest). No model training. This package must stay importable **without** the backend.

```
data_engineering/
  sample_datasets/   generate_sample.py, generated small/ and medium/ datasets, README.md (planted patterns)
  data_validation/   validate_dataset(tables) -> list[ValidationIssue]
  test_scenarios/    edge-case datasets (empty, duplicates, dangling references, single class, ...)
  documentation/     test_cases.md with hand-computed examples
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r data_engineering/requirements.txt
python -m pytest tests -q
```

## Rules for this module

- Datasets are **synthetic and seeded**. Never commit real employee data.
- Generated data must be learnable: role assignment correlates with attributes with a little noise. Document the planted pattern in `sample_datasets/README.md`; never feed the ground truth to the ML pipeline.
- File columns follow `docs/modules/DATA_PIPELINE.md` section 1. Issue codes follow `docs/modules/VALIDATION.md` section 1.
- Cross-module tests live in `tests/` (also yours).

Guide: `docs/team_guides/SHWETA_GUIDE.md`.

## Generating datasets

```bash
# from the repo root
python data_engineering/sample_datasets/generate_sample.py --size small  --seed 42 --out data_engineering/sample_datasets/small
python data_engineering/sample_datasets/generate_sample.py --size medium --seed 42 --out data_engineering/sample_datasets/medium
```

Same seed → byte-identical output every time. See `sample_datasets/README.md` for the planted pattern.

## Running validation manually

```python
import pandas as pd
from data_engineering.data_validation import validate_dataset

tables = {name: pd.read_csv(f"data_engineering/sample_datasets/small/{name}.csv")
          for name in ["users","roles","permissions","resources","user_roles","role_permissions"]}
issues = validate_dataset(tables)
print(f"errors: {sum(1 for i in issues if i['severity']=='error')}")
print(f"warnings: {sum(1 for i in issues if i['severity']=='warning')}")
```

## Running the authorisation oracle

```python
from data_engineering.data_validation import brute_force_auth
auth_df = brute_force_auth(tables["users"], tables["roles"], tables["permissions"],
                            tables["user_roles"], tables["role_permissions"], tables["resources"])
print(auth_df.head())
```

## Running tests

```bash
# from the repo root
python -m pytest tests -q
# or just Shweta's tests
python -m pytest tests/test_data_validation.py tests/test_dataset_generation.py -v
```

## Status

Implementation complete. All assigned tasks implemented:
- `sample_datasets/generate_sample.py` + generated `small/` and `medium/` datasets
- `data_validation/validator.py` — all 12 issue codes
- `data_validation/oracle.py` — brute_force_auth + verify_samples
- `test_scenarios/` — 14 edge-case scenario files
- `documentation/test_cases.md` — hand-computed examples
