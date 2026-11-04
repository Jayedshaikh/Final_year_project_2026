# GRANTHALI.md — Agent instructions for Granthali Sandesh Mahajan

**Role:** Security Logic and ABAC Policy Engineer · **Branch:** `feature/granthali-policy-engine`
**Full guide:** `docs/team_guides/GRANTHALI_GUIDE.md` (read it first). Global rules: `AGENTS.md`, `PROJECT_RULES.json`.

## You may edit (OWNER)
`policy_engine/**`. You may propose `config/` keys through a PR reviewed by Jayed.

## You must NOT edit
`backend/**`, `frontend/**`, `data_engineering/**`, `shared/**`. Do not train ML models. Do not import from `backend`.

## Do in this order
1. `schemas/`: rule dataclass/model aligned with `ABACRule` and `Condition` in `shared/schemas/contracts.py`; rule evaluation against a user and resource attribute row.
2. RBAC authorisation verification (`UA` and `PA` to the access matrix) as a library function.
3. Support and confidence calculation.
4. `rule_merger/`, `rule_generalizer/`, `rule_pruner/` (remove covered and redundant rules).
5. `policy_validator/`: precision, recall, F1, OPR, UPR, rule count, WSC on the full matrix; fail-safe deny.
6. `policy_exporter/`: JSON and XACML-style export of approved rules only.
7. Expose the public API in `policy_engine/__init__.py`: `optimise_policy`, `validate_policy`, `export_policy`.

## Key constraints
Pure Python plus pandas. Optimisation must never reduce coverage of positives silently; report the change in metrics. Unknown attribute or evaluation error means deny. Export refuses any rule not `approved`.

## Done means
Public functions match `docs/modules/POLICY_ENGINE.md`, tests pass on tiny data, and Jayed can call the three functions without changes to your internals.
