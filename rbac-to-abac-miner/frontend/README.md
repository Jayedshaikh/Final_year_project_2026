# frontend/

Owner: **Naeem**. React + Vite + Tailwind CSS. The UI displays API data and holds no ML or policy logic.

## Setup

Scaffold the app on your first task (commands are in `docs/modules/FRONTEND.md`), then:

```bash
cd frontend
cp .env.example .env        # VITE_USE_MOCKS=true by default
npm install
npm run dev                 # http://localhost:5173
npm run build               # must pass; CI runs it
```

## Mock mode (start here, do not wait for the backend)

With `VITE_USE_MOCKS=true`, `src/services/mockApi.js` returns copies of `shared/sample_responses/*.json`. Copy those files into `src/services/mocks/` unchanged. When a backend endpoint is live, set `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL=http://localhost:8000/api/v1`.

## Manual test checklist (fill in as pages are completed)

- [ ] Upload: valid dataset shows summary; invalid mock shows errors (red) and warnings (amber)
- [ ] Dataset: counts and authorisation density shown
- [ ] Training: form submits `TrainingConfigRequest`; progress state; result stored in context
- [ ] Models: table + chart; Decision Tree badge; `f1_target_met` shown
- [ ] Rules: readable rule text, support, confidence, status chip
- [ ] Metrics: Precision, Recall, F1, OPR, UPR, rule count, WSC with "full access matrix" caption
- [ ] Review: approve / reject / edit per rule; no approve-all; builds `ApprovalRequest`
- [ ] Export: disabled until a rule is approved; JSON and XACML preview and download
- [ ] Error mock (`error_response.json`) renders a readable banner on every page

Docs: `docs/modules/FRONTEND.md`, guide `docs/team_guides/NAEEM_GUIDE.md`.
