# RBAC-to-ABAC Miner

**Supervised Learning Based Approach for Mining ABAC Rules from Existing RBAC Enabled Systems**
Final-year academic prototype. Four developers, one repository, one shared set of contracts.

> Status: governance and scaffolding only. No application code is implemented yet. Start with your guide in `docs/team_guides/`.

## Problem statement

Organisations run on Role-Based Access Control (RBAC), which becomes hard to maintain as roles multiply. Attribute-Based Access Control (ABAC) is more expressive but writing ABAC policies by hand is slow. This project mines ABAC rules automatically from an existing RBAC state using supervised learning.

## Objectives

1. Import RBAC data (users, roles, permissions, UA, PA) and user/resource attributes.
2. Build the RBAC authorisation relation and generate positive and sampled negative examples.
3. Train and compare Decision Tree, Random Forest and Gradient Boosting.
4. Extract permit paths from the Decision Tree as candidate ABAC rules.
5. Merge, generalise and prune rules; validate against the full RBAC access matrix.
6. Let an administrator review and approve rules; export JSON and XACML-style policies.

## Features

Dataset upload and validation, authorisation matrix, model comparison, rule extraction, policy optimisation, metrics (precision, recall, F1, over-privilege rate, under-privilege rate, rule count, WSC), approval workflow, policy export.

Out of scope: live policy decision point/IAM integration, environmental attributes, deny-rule mining.

## Architecture

```
React UI (Naeem)  --REST-->  FastAPI backend (Jayed)  --calls-->  policy_engine (Granthali)
                                   |
                           data_pipeline + ml_engine
Shared contracts: shared/schemas/contracts.py     Data and tests: data_engineering + tests (Shweta)
```

Details: `PROJECT_ARCHITECTURE.md`.

## Technology stack

Python 3.9+, FastAPI, Pydantic v2, Pandas, NumPy, scikit-learn, XGBoost, imbalanced-learn, SHAP, Joblib, Pytest; React, Vite, Tailwind CSS, Recharts; CSV and JSON storage; Git and GitHub.

## Installation

```bash
git clone <repo-url> && cd rbac-to-abac-miner
git checkout develop
git checkout -b feature/<your-branch>      # see PROJECT_RULES.json for your branch name
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-base.txt        # governance validation + contracts
```

Each member installs only what their guide lists (Jayed: `backend/requirements.txt`; Naeem: `npm install` in `frontend/`; Shweta and Granthali: pandas, numpy, pytest, pydantic).

## Execution (once modules exist)

```bash
uvicorn backend.app.main:app --reload --port 8000     # backend
cd frontend && npm run dev                            # frontend
```

## Folder structure

```
backend/            Jayed    app, api, services, data_pipeline, ml_engine, models, schemas, utils, tests
frontend/           Naeem    React + Vite + Tailwind
data_engineering/   Shweta   sample_datasets, data_validation, test_scenarios, documentation
policy_engine/      Granthali schemas, rule_merger, rule_generalizer, rule_pruner, policy_validator, policy_exporter, tests
shared/             All      schemas (contracts.py), api_contracts, sample_responses (mocks)
tests/              Shweta   cross-module tests
docs/               All      architecture, modules, team_guides, development_rules
config/             Jayed    thresholds, seeds
scripts/                     validate_governance.py
PROJECT_RULES.json           governance (machine-readable)
AGENTS.md, JAYED.md, NAEEM.md, SHWETA.md, GRANTHALI.md   AI agent instructions
```

## Team

| Member | Role | Owns |
|---|---|---|
| Jayed Altaf Shaikh | ML Engineer, Backend Lead, integration lead | `backend/` |
| Naeem Julfekar Shaikh | Frontend Engineer | `frontend/` |
| Shweta Suresh Kidile | Data Engineering and QA | `data_engineering/`, `tests/` |
| Granthali Sandesh Mahajan | Security Logic and ABAC Policy Engineer | `policy_engine/` |

Project-level decisions are shared among all four members.

## Testing

```bash
python scripts/validate_governance.py
python -m pytest -q
```

## Where to start

Read `DEVELOPMENT.md`, then your guide in `docs/team_guides/`, then `ROADMAP.md`.
