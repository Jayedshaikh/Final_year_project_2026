# NAEEM.md — Agent instructions for Naeem Julfekar Shaikh

**Role:** Frontend Engineer · **Branch:** `feature/naeem-frontend`
**Full guide:** `docs/team_guides/NAEEM_GUIDE.md` (read it first). Global rules: `AGENTS.md`, `PROJECT_RULES.json`.

## You may edit (OWNER)
`frontend/**` only.

## You must NOT edit
`backend/**`, `policy_engine/**`, `data_engineering/**`, `tests/**`, `shared/**`. Never implement ML or rule logic in the UI.

## Do in this order
1. Scaffold Vite + React + Tailwind + Recharts in `frontend/` (`npm create vite@latest`).
2. Add `src/services/api.js` with a mock switch: `VITE_USE_MOCKS=true` reads copies of `shared/sample_responses/*.json`; otherwise calls `VITE_API_BASE_URL`.
3. Layout and navigation, then pages: Upload, Dataset Preview, Training Config, Model Comparison, Metrics, Rules, Review (approve/reject/edit), Export.
4. Show precision, recall, F1, OPR, UPR, rule count and WSC exactly as returned by the API; compute nothing yourself.
5. Handle loading, empty and `ErrorResponse` states on every page.
6. Switch to the real backend once Jayed's endpoints match the contracts.

## Key constraints
Mock data must match `shared/schemas/contracts.py` exactly. Never add or rename fields. Approval is always an explicit user click; there is no "approve all" default. The Export page only offers approved rules.

## Done means
`npm run build` passes, each page works with mocks, and the full flow works against the real backend.
