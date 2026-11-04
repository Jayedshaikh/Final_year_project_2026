# JAYED.md — Agent instructions for Jayed Altaf Shaikh

**Role:** ML Engineer and Backend Lead · **Branches:** `feature/jayed-backend`, `feature/jayed-ml-engine`
**Full guide:** `docs/team_guides/JAYED_GUIDE.md` (read it first). Global rules: `AGENTS.md`, `PROJECT_RULES.json`.

## You may edit (OWNER)
`backend/**`, `shared/**` (restricted: needs all-member approval), `docs/**`, `config/`, root governance files (restricted).

## You must NOT edit
`frontend/**` (Naeem), `policy_engine/**` (Granthali), `data_engineering/**` and `tests/**` (Shweta, except contract/integration tests you add via PR).
Do not implement rule merging/generalisation/pruning/WSC/export. Call `policy_engine` instead.

## Do in this order
1. FastAPI skeleton with `/health`, CORS from config, router stubs returning contract-valid mocks.
2. RBAC loader and authorisation matrix (`backend/data_pipeline/`).
3. Positive/negative sample generation, encoding (fit on train only).
4. Train DT, RF, GB with CV and fixed seed (`backend/ml_engine/`).
5. Decision Tree permit-path extraction into `ABACRule` objects with support and confidence.
6. Services layer calling `policy_engine.optimise_policy`, `validate_policy`, `export_policy`.
7. Real endpoints replacing stubs; response models from `shared/schemas/contracts.py`.

## Key constraints
Rules come from the Decision Tree only. Validate on the full matrix. No GPU. Share results as JSON, not model binaries.

## Done means
Tests pass, endpoints match contracts, `backend/README.md` explains how to run, and Shweta's API tests pass.
