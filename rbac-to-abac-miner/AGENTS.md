# AGENTS.md — Instructions for AI coding agents

This repository is the final-year project **"Supervised Learning Based Approach for Mining ABAC Rules from Existing RBAC Enabled Systems"**. Four developers work in parallel on separate modules. These rules apply to any AI coding agent (Claude Code, Cursor, Copilot, OpenCode, etc.).

## Before writing any code

1. Read `PROJECT_RULES.json`. It defines module ownership, permissions and prohibited practices.
2. Find out **which member you are working for** (ask if unclear) and read their guide in `docs/team_guides/` and their short file (`JAYED.md`, `NAEEM.md`, `SHWETA.md` or `GRANTHALI.md`).
3. Read `shared/schemas/contracts.py` and the module doc in `docs/modules/` for the area you will touch.
4. Inspect existing code before creating new files.

## Mandatory behaviour

1. Follow the existing architecture (`PROJECT_ARCHITECTURE.md`).
2. Respect module ownership: only edit paths the current member OWNS. If a task needs a change elsewhere, stop and say which owner must approve it.
3. Never modify unrelated modules.
4. Follow approved API contracts. Never invent undocumented data structures or fields.
5. Never silently change `shared/` (schemas, api_contracts, sample_responses). Propose a change request instead.
6. Never introduce new dependencies without approval.
7. Write tests for every new function; run them before saying you are done.
8. Update the relevant module doc and README when an interface changes.
9. Never remove working functionality.
10. Never claim a feature is implemented, or tests pass, unless you ran them and saw the result.
11. If requirements conflict (guide vs. rules vs. report), report the conflict and wait. Do not choose silently.
12. Where the report is silent, label your choice as an **implementation decision** and record it in `docs/development_rules/DECISIONS.md`.

## Algorithm guard rails (do not violate)

- The **Decision Tree** is the only rule-extraction model. Random Forest and Gradient Boosting are accuracy references.
- Final policy metrics are computed on the **full access matrix**, never only on sampled negatives.
- Never train, tune or fit encoders/imputers on the test split. Use fixed seeds (default 42).
- Rules are `permit` rules only. No deny-rule mining. No environmental attributes. No live IAM/PDP integration.
- Never auto-approve a rule. Only rules with `status == "approved"` can be exported.
- On any evaluation failure the decision is **deny** (fail safe), never allow.
- Never fabricate evaluation numbers. Never hardcode metric values outside `shared/sample_responses/` mocks.

## Safety and hygiene

- No real employee data, secrets or `.env` files in commits.
- No direct commits to `main` or `develop`; work on your feature branch and open a PR.
- Do not commit trained model binaries or large datasets.
- Keep GPU-free and CPU-friendly; low-spec laptops (Shweta, Granthali) must be able to run their modules and tests.

## Quick commands

```bash
python scripts/validate_governance.py      # governance + contract check
python -m pytest -q                        # all tests that exist
```

## When finished

Report: files changed, tests run with real output summary, any contract or ownership issues found, and open questions.
