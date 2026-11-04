# tests/ (cross-module tests)

Owner: **Shweta**. Jayed and Granthali are contributors (they may add tests for their integration points through a PR that Shweta reviews).

Planned files (Shweta creates them, see her guide): `test_data_validation.py`, `test_dataset_generation.py`, `test_api.py`, `test_integration.py`.

Module-level unit tests live with their module: `backend/tests/` (Jayed), `policy_engine/tests/` (Granthali), `shared/tests/` (contracts).

```bash
python -m pytest -q                       # everything that exists
python -m pytest tests -q                 # only cross-module tests
```

Tests that need an unfinished module use `pytest.mark.skipif` and say why. A skipped test is not a pass: list skips in the PR.
