# backend/

Owner: **Jayed**. Python 3.9+, FastAPI, Pydantic v2, pandas, scikit-learn. CPU only.

## Layout

```
backend/
  app/            main.py (FastAPI app, CORS, router wiring, exception handlers)
  api/            route handlers, one file per resource (datasets, training, policies)
  services/       pipeline_service.py (orchestration), run store
  data_pipeline/  loader, preprocess, auth_matrix, sampling
  ml_engine/      train, evaluate, extract_rules
  schemas/        thin wrappers/re-exports of shared contracts (never redefine them)
  utils/          seed, timing, storage, config loader
  models/         saved models (git-ignored)
  tests/          unit and contract tests
  requirements.txt
```

## Setup and run

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000      # run from the repository root
python -m pytest backend/tests -q
```

Environment variables: `FRONTEND_ORIGIN` (default `http://localhost:5173`), `BACKEND_STUBS=true` to serve `shared/sample_responses/` instead of real logic (day-1 integration mode).

## Rules for this module

- Response bodies are built from `shared/schemas/contracts.py` models only.
- Calls into `policy_engine` go through `backend/services/` and use only its public functions (`docs/modules/POLICY_ENGINE.md`).
- Rules are extracted from the Decision Tree only. Policy metrics come from `policy_engine.validate_policy` on the full access matrix.
- Never commit models, runs, uploads or real data.

Docs: `docs/modules/DATA_PIPELINE.md`, `ML_ENGINE.md`, `API.md`, `DATA_CONTRACTS.md`. Guide: `docs/team_guides/JAYED_GUIDE.md`.

## Status

Scaffold only. Jayed fills this file with real run instructions and the demo seed when each task in his guide completes.
