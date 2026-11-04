# SHWETA.md — Agent instructions for Shweta Suresh Kidile

**Role:** Data Engineering and QA Engineer · **Branch:** `feature/shweta-data-qa`
**Full guide:** `docs/team_guides/SHWETA_GUIDE.md` (read it first). Global rules: `AGENTS.md`, `PROJECT_RULES.json`.

## You may edit (OWNER)
`data_engineering/**`, `tests/**`.

## You must NOT edit
`backend/**`, `frontend/**`, `policy_engine/**`, `shared/**`. Do not train models. Keep every dataset small and lightweight.

## Do in this order
1. Study the RBAC data model in `docs/modules/DATA_PIPELINE.md` and `DATA_CONTRACTS.md`.
2. Write a seeded generator `data_engineering/sample_datasets/generate_sample.py` producing the six CSVs plus JSON equivalents (tiny: about 12 users, 4 roles, 8 resources; and a medium set).
3. Write `data_engineering/data_validation/` (missing values, duplicates, dangling references, invalid attribute values) returning `ValidationIssue`-shaped results.
4. Write an independent brute-force authorisation checker to cross-verify Jayed's matrix.
5. Write `tests/test_data_validation.py`, `test_dataset_generation.py`, `test_api.py`, `test_integration.py`, plus `data_engineering/documentation/test_cases.md`.
6. Verify evaluation outputs against independently calculated values.

## Key constraints
Synthetic data only. No real employee data. Expected values in tests are computed independently, never copied from model output.

## Done means
Datasets reproducible from a seed, validators catch each seeded defect, tests run in seconds on a low-end laptop.
