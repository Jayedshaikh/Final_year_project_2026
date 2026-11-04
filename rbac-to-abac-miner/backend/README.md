# backend/

**Owner:** Jayed Altaf Shaikh. Python 3.9+, FastAPI, Pydantic v2, pandas, scikit-learn. CPU only.

## Layout

```
backend/
  app/            FastAPI entry point, CORS, router wiring, exception handlers
  api/            Route handlers — datasets.py, training.py, policies.py
  services/       pipeline_service.py (orchestration), state_store.py
  data_pipeline/  loader.py, preprocess.py, auth_matrix.py, sampling.py
  ml_engine/      train.py, evaluate.py, extract_rules.py
  schemas/        Re-exports of shared/schemas/contracts.py (never redefines them)
  utils/          seed.py, timing.py, storage.py, config.py
  models/         Saved .joblib model files (git-ignored)
  runs/           In-memory + JSON state persistence (git-ignored)
  tests/          Unit and contract tests
  requirements.txt
```

## Setup

Run all commands from the **repository root** (`rbac-to-abac-miner/`).

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install backend dependencies
pip install -r backend/requirements.txt
```

## Running the server

```bash
uvicorn backend.app.main:app --reload --port 8000
```

The API is then available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`  
Health check: `http://localhost:8000/health`

**Environment variables:**

| Variable | Default | Purpose |
|---|---|---|
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allowed origin |
| `BACKEND_STUBS` | `false` | Set `true` to serve `shared/sample_responses/` (day-1 mock mode) |

## Running tests

```bash
python -m pytest backend/tests -q
python -m pytest backend/tests shared/tests -q   # includes contract tests
```

All 85 tests pass on Python 3.9+.

## Demo — full end-to-end flow (seed=42, seed_hospital dataset)

```bash
python scripts/run_demo.py --inline
```

**Expected output with seed_hospital dataset + seed=42:**

```
[1] dataset_id=ds_001  users=12  roles=5  permissions=3  resources=8
[2] total_tuples=288  authorised=200  density=0.694
[3] run_id=run_001  train=230  test=58  f1_target_met=True
    decision_tree     f1=1.0000  p=1.0000  r=1.0000  time≈0.002s
    random_forest     f1=1.0000  p=1.0000  r=1.0000  time≈0.218s
    gradient_boosting f1=1.0000  p=1.0000  r=1.0000  time≈0.148s
[4] selected_for_extraction: decision_tree
[5] n_rules=1  (R001, action=read, support=0.352, confidence=1.000)
[6] policy_id=pol_001  rules_before=1  rules_after=1  policy_f1=1.000
[7] precision=1.000  recall=1.000  f1=1.000  OPR=0.000  UPR=0.000  WSC=2.0
[8] approved=1  rejected=0  unreviewed=0
[9] n_rules_exported=1  default_decision=deny
```

> **Note:** F1=1.0 on the seed_hospital dataset is expected because it has clear
> department/role patterns that the Decision Tree captures perfectly. The demo
> uses `min_support=0.01, min_confidence=0.8` — adjust in `TrainingConfigRequest`
> to explore threshold effects.

## API endpoints (all under `/api/v1`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/datasets/upload` | Upload 6 CSV/JSON RBAC files |
| `GET` | `/datasets/{id}/authorisation` | Auth matrix summary |
| `POST` | `/training/run` | Train DT, RF, GB |
| `GET` | `/training/{run_id}/comparison` | Model comparison table |
| `GET` | `/training/{run_id}/rules` | Extracted ABAC rules |
| `POST` | `/policies/optimise/{run_id}` | Optimise rules via policy engine |
| `GET` | `/policies/{id}/validation` | Validate against full matrix |
| `POST` | `/policies/{id}/review` | Approve / reject / edit rules |
| `POST` | `/policies/{id}/export` | Export approved rules (JSON or XACML) |

Response shapes: `shared/schemas/contracts.py`. Errors always use `ErrorResponse`.

## Stub mode (for Naeem's frontend and Shweta's API tests)

```bash
BACKEND_STUBS=true uvicorn backend.app.main:app --reload --port 8000
```

Returns canned responses from `shared/sample_responses/` so the frontend and
API tests can integrate before real training is needed.

## Policy engine integration

`policy_engine` calls (optimise, validate, export) are **stubbed** until
Granthali's module is complete. The stubs are clearly marked in
`backend/services/pipeline_service.py`. When `policy_engine` exposes its public
functions (`optimise_policy`, `validate_policy`, `export_policy`), the backend
will automatically use them — no code change needed beyond importing.

## Rules for this module

- Response bodies are built only from `shared/schemas/contracts.py` models.
- Rules are extracted from the Decision Tree only (never RF or GB).
- Policy metrics are computed on the **full access matrix**, not sampled data.
- Never commit model binaries, runs state, uploads, or real employee data.
- All stochastic steps use an explicit `random_seed` (default 42).

## Docs

- Pipeline: `docs/modules/DATA_PIPELINE.md`
- ML engine: `docs/modules/ML_ENGINE.md`
- API behaviour: `docs/modules/API.md`
- Data contracts: `docs/modules/DATA_CONTRACTS.md`
- Guide: `docs/team_guides/JAYED_GUIDE.md`
