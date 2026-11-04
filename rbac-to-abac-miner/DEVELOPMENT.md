# DEVELOPMENT.md

## 1. One-time repository setup (Jayed, 15 minutes)

```bash
cd rbac-to-abac-miner
git init -b main
git add . && git commit -m "chore: initial governance scaffold"
git remote add origin <github-url>
git push -u origin main
git checkout -b develop && git push -u origin develop
```

On GitHub (Settings, Branches): protect `main` and `develop`: require a pull request, require 1 approval, require the `CI` status check, block force pushes. Add the other three as collaborators. Edit `.github/CODEOWNERS` with real GitHub usernames. Optionally set `develop` as the default branch.

Branch protection is what actually enforces the rules; `PROJECT_RULES.json` alone cannot.

## 2. Each member's setup

```bash
git clone <github-url> && cd rbac-to-abac-miner
git checkout develop
git checkout -b feature/<your-branch>
```

| Member | Branch |
|---|---|
| Jayed | `feature/jayed-backend`, `feature/jayed-ml-engine` |
| Naeem | `feature/naeem-frontend` |
| Shweta | `feature/shweta-data-qa` |
| Granthali | `feature/granthali-policy-engine` |

Then follow your guide in `docs/team_guides/`. If you use an AI coding agent, point it at `AGENTS.md` and your personal file.

## 3. Daily workflow

1. `git checkout develop && git pull`, then `git checkout <your-branch> && git merge develop` (or rebase) every morning.
2. Work only in modules you own (see `PROJECT_RULES.json` `modules`).
3. Small commits, run tests, push, open a PR into `develop` at least every 2 days.

## 4. Branch strategy

```
main        stable milestone releases only
develop     integration branch; PRs only
feature/*   one per member/area; fix/<member>-<topic> for bug fixes
```

## 5. Commit conventions

`type(scope): summary` with types `feat, fix, docs, test, refactor, chore`.
Examples: `feat(policy_engine): add rule merger`, `test(data_engineering): add dangling reference cases`.

## 6. Pull request requirements

- Touches only modules you own, or approved contributor paths.
- Description: what changed, which milestone, how tested.
- Tests added and passing; docs updated if an interface changed.
- `python scripts/validate_governance.py` passes.
- One reviewer who is not the author. If the PR touches someone else's module, that owner must approve.
- Jayed merges into `develop`; Jayed's own PRs need another member's approval.

## 7. Changing a shared contract

1. Open an issue/PR using `docs/development_rules/CHANGE_REQUEST_TEMPLATE.md`.
2. All four members approve in the PR.
3. Update `contracts.py`, bump `CONTRACT_VERSION`, regenerate `shared/sample_responses/`, update `docs/modules/DATA_CONTRACTS.md` and `PROJECT_RULES.json` metadata.
4. Every consumer adapts in the same week.

## 8. Module integration procedure

1. The module passes its own tests and has its README.
2. The owner announces the public interface (function signature or endpoint) is stable.
3. The consumer integrates in a PR to their own module only.
4. Shweta's integration test for that interface passes.
5. Record the integration in `ROADMAP.md` progress table.

## 9. Testing procedure

```bash
python scripts/validate_governance.py
python -m pytest -q                       # everything
python -m pytest policy_engine/tests -q   # one module
cd frontend && npm run build
```

Tests must be seeded and fast. Expected values come from independent calculation.

## 10. Release procedure

At the end of a milestone: all tests green on `develop`, ROADMAP updated, PR `develop` to `main`, reviewed by all four, tag `v0.<milestone>.0`.

## 11. Weekly rhythm (suggested)

Monday: 20-minute sync, confirm interfaces. Friday: demo what works end to end, merge to `develop`, update ROADMAP.
