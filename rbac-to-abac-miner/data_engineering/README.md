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

## Status

Scaffold only. Shweta's first deliverable is `generate_sample.py` and the `small` dataset (hand it to Jayed on day 2).
