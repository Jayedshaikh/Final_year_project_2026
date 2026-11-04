# JAYED.md — Agent instructions for Jayed Altaf Shaikh

**Role:** ML Engineer and Backend Lead · **Branches:** `feature/jayed-backend`, `feature/jayed-ml-engine`
**Full guide:** `docs/team_guides/JAYED_GUIDE.md` (read it first). Global rules: `AGENTS.md`, `PROJECT_RULES.json`.

## You may edit (OWNER)
`backend/**`, `shared/**` (restricted: needs all-member approval), `docs/**`, `config/`, root governance files (restricted).

## You must NOT edit
`frontend/**` (Naeem), `policy_engine/**` (Granthali), `data_engineering/**` and `tests/**` (Shweta, except contract/integration tests you add via PR).
Do not implement rule merging/generalisation/pruning/WSC/export. Call `policy_engine` instead.

## Implementation status

### ✅ Completed (Tasks 1–8)
1. FastAPI skeleton — `/health`, CORS, router stubs, `BACKEND_STUBS` mode
2. RBAC loader and auth matrix (`backend/data_pipeline/`)
3. Positive/negative sample generation, encoding (fit on train only)
4. Train DT, RF, GB with CV and fixed seed (`backend/ml_engine/`)
5. Decision Tree permit-path extraction into `ABACRule` objects
6. Services layer calling `policy_engine` stubs (real calls activate once Granthali's module is ready)
7. Real endpoints replacing stubs; response models from `shared/schemas/contracts.py`
8. Demo script `scripts/run_demo.py --inline` runs full pipeline

### 🔄 Pending (waiting on other members)
- Replace TEMPORARY support/confidence helper with `policy_engine` functions (Granthali)
- Replace optimise/validate/export stubs with real `policy_engine` calls (Granthali)
- Shweta's API integration tests (`tests/test_api.py`)

## Key constraints
- Rules come from the Decision Tree only. Never RF or GB.
- Validate on the full matrix. No GPU. Share results as JSON, not model binaries.
- Policy metrics: `policy_engine.validate_policy` on full access matrix (not sampled negatives).

## Done means
Tests pass (99/99), endpoints match contracts, `backend/README.md` explains how to run, and Shweta's API tests pass.

## Quick commands
```bash
# From repository root:
python -m pytest backend/tests shared/tests -q         # 99 tests, all pass
python scripts/run_demo.py --inline                     # end-to-end demo
uvicorn backend.app.main:app --reload --port 8000       # run server
```
