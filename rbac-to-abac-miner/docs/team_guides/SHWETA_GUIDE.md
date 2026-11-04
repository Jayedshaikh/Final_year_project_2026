# Development Guide — Shweta Suresh Kidile

**Designation:** Data Engineering and Quality Assurance Engineer
**Branch:** `feature/shweta-data-qa`
**Hardware:** Low-specification laptop. Your work uses small CSV/JSON files and lightweight Python only. You never train models.

## 1. Primary objective

Make sure the whole system is fed correct data and tested properly. You produce reproducible synthetic RBAC datasets, data-validation logic, an independent authorisation checker and the test suite (unit, API, integration, end-to-end) that proves the other modules meet their contracts.

## 2. Exact module ownership (OWNER)

```
data_engineering/
├── sample_datasets/      generator script and generated CSV/JSON
├── data_validation/      validation library
├── test_scenarios/       edge-case datasets
└── documentation/        test_cases.md, dataset notes
tests/
├── test_data_validation.py
├── test_dataset_generation.py
├── test_api.py
└── test_integration.py
```

Jayed and Granthali may add contract tests under `tests/` via PR (CONTRIBUTOR). Read-only for you: `backend/`, `frontend/`, `policy_engine/`, `shared/`.

## 3. Responsibilities

1. Understand the RBAC data structure.
2. Prepare seeded synthetic datasets.
3. Create sample CSV and JSON files.
4. Validate user, role and permission relationships.
5. Identify missing and inconsistent attributes.
6. Prepare test datasets of different sizes.
7. Validate positive and negative samples.
8. Prepare edge cases.
9. Test backend APIs.
10. Verify evaluation outputs against independently calculated results.

## 4. Tasks in implementation order

### Task 1 — Understand the model (Milestone 2, day 1)
Read `docs/modules/DATA_PIPELINE.md` and `DATA_CONTRACTS.md`. Draw by hand a 3-user, 2-role, 3-resource example and write down its authorised tuples. This becomes your first test oracle.

### Task 2 — Dataset generator
`data_engineering/sample_datasets/generate_sample.py --size small|medium --seed 42 --out <dir>` writes:

`users.csv` (user_id, department, seniority, clearance), `roles.csv` (role_id, role_name), `permissions.csv` (permission_id, action), `resources.csv` (resource_id, department, sensitivity, type), `user_roles.csv` (user_id, role_id), `role_permissions.csv` (role_id, permission_id), plus the same content as JSON.

Make the data **learnable**: role assignments should correlate with attributes (for example Finance users hold the Finance role) with a small amount of noise, so the Decision Tree has real patterns to find. Document the planted pattern in `data_engineering/sample_datasets/README.md` (the generator's ground truth is useful for QA, but never leaked into the ML pipeline).

Sizes: small about 12 users, 4 roles, 8 resources (for unit tests); medium about 200 users, 8 roles, 100 resources (for demo). Both must run in seconds.

*Implementation decision to confirm with Jayed:* how permissions relate to resources (action plus optional resource scope). Record the outcome in `docs/development_rules/DECISIONS.md`.

### Task 3 — Validation library (Milestone 2)
`data_engineering/data_validation/validator.py`:
`validate_dataset(files: dict[str, DataFrame]) -> list[ValidationIssue-like dict]` checking: missing files and columns, missing values, duplicate keys, dangling references (user_roles pointing to unknown users/roles, role_permissions pointing to unknown roles/permissions), invalid attribute values (negative seniority, unknown category), empty files. Output dictionaries must match `ValidationIssue` fields in `contracts.py` (`severity`, `code`, `file`, `row`, `column`, `message`).

### Task 4 — Independent authorisation oracle
`data_engineering/data_validation/oracle.py`: `brute_force_auth(users, roles, permissions, ua, pa, resources)` implemented with plain loops (not pandas merges) so it is independent of Jayed's and Granthali's code. Use it to cross-check their matrices.

### Task 5 — Sample verification
`verify_samples(auth_df, samples_df)`: all positives are in Auth, no negative is in Auth, no duplicates, label balance matches the requested ratio, no overlap between train and test rows.

### Task 6 — Edge-case scenarios (`test_scenarios/`)
Empty users file, user with no roles, role with no permissions, duplicate user_id, dangling role reference, missing attribute column, all-authorised dataset, none-authorised dataset, single-class data, unicode names, very small dataset (3 users).

### Task 7 — Tests
`tests/test_data_validation.py`, `tests/test_dataset_generation.py` (same seed gives identical files), `tests/test_api.py` (uses `httpx`/`TestClient` against Jayed's app and validates every response with the Pydantic models), `tests/test_integration.py` (upload to export flow). Mark tests that need the backend with `@pytest.mark.skipif` until it exists.

### Task 8 — QA of evaluation outputs
Hand-compute precision, recall, F1, OPR, UPR for a tiny policy and compare with `policy_engine.validate_policy` output. Record formulas and the worked example in `data_engineering/documentation/test_cases.md`.

### Task 9 — Test documentation
`data_engineering/documentation/test_cases.md`: table of test id, purpose, input, expected result, status. Update it every time you add a test.

## 5. Required files

See sections 2 and 4. Also `data_engineering/README.md` explaining how to generate data and run validation.

## 6. Input and output contracts

Datasets: `docs/modules/DATA_CONTRACTS.md` (file columns). Validation results: `ValidationIssue` in `shared/schemas/contracts.py`. API responses to be verified: all models in `contracts.py`.

## 7. Dependencies

Only `pandas`, `numpy`, `pytest`, `httpx`, `pydantic`. No scikit-learn needed. Your validators must be importable without the backend.

## 8. Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pandas numpy pytest httpx "pydantic>=2"
```

## 9. Commands

```bash
python data_engineering/sample_datasets/generate_sample.py --size small --seed 42 --out data_engineering/sample_datasets/small
python -m pytest tests -q
python scripts/validate_governance.py
```

## 10. Testing instructions

Tests must run in seconds on a low-end laptop. Expected values come from your oracle or hand calculation, never from model output copied into the test (that would hide bugs).

## 11. Integration instructions

- Hand Jayed the `small` dataset path on day 2 so his loader has real input.
- Hand Granthali a tiny dataset with hand-computed answers for her validator.
- Report bugs as GitHub issues to the module owner. Do not edit their code.

## 12. Restrictions

- No model training, no large datasets, no real employee data.
- Do not edit `backend/`, `frontend/`, `policy_engine/`, `shared/`.
- Do not hardcode expected metrics from model output.

## 13. Completion criteria

- Generator reproducible from seed; small and medium datasets committed (small only if size is a concern).
- Validator detects every planted defect in `test_scenarios/`.
- Oracle matches the backend's Auth matrix on all sample datasets.
- API and integration tests exist and pass against the live backend.
- `test_cases.md` is complete.

## 14. Common mistakes to avoid

- Writing tests that copy the code under test (use the independent oracle).
- Random, non-seeded datasets.
- Datasets with no learnable pattern (the ML demo will look broken).
- Fixing other members' bugs yourself instead of reporting them.
- Forgetting edge cases such as empty or single-class data.
