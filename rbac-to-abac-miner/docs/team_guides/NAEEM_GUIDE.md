# Development Guide — Naeem Julfekar Shaikh

**Designation:** Frontend Engineer
**Branch:** `feature/naeem-frontend`
**Hardware:** Normal laptop. You never need trained models or the backend to start.

## 1. Primary objective

Build the administrator web interface that lets a user upload an RBAC dataset, configure and view model training, compare models, review mined ABAC rules, approve or reject them, and export the approved policy as JSON or XACML-style XML. The UI displays what the API returns; it contains no ML or policy logic.

## 2. Exact module ownership (OWNER)

`frontend/` and everything inside it:

```
frontend/
├── src/
│   ├── components/   reusable UI parts
│   ├── pages/        one file per screen
│   ├── layouts/      app shell, sidebar, header
│   ├── services/     api.js, mockApi.js (only place that does HTTP)
│   ├── hooks/        useApi, useUpload, useRun
│   ├── context/      WorkflowContext (dataset_id, run_id, policy_id)
│   └── utils/        formatters
├── public/
├── package.json
└── README.md
```

Read-only for you: everything else, especially `shared/sample_responses/` and `shared/schemas/contracts.py`.

## 3. Responsibilities

1. Application layout and navigation.
2. Administrator dashboard.
3. RBAC upload interface (CSV/JSON).
4. Dataset preview and attribute visualisation.
5. Model training configuration.
6. Training progress.
7. Model comparison dashboard.
8. Precision, recall, F1, OPR (and UPR, rule count, WSC) display.
9. ABAC rule visualisation.
10. Rule approval, rejection and edit.
11. JSON and XACML export.

## 4. Tasks in implementation order

1. **Scaffold** (Milestone 9): `npm create vite@latest frontend -- --template react`, add Tailwind CSS, `react-router-dom`, `recharts`.
2. **API layer**: `src/services/api.js` exposes one function per endpoint. If `VITE_USE_MOCKS=true`, it returns the JSON from copies of `shared/sample_responses/` placed in `frontend/src/services/mocks/` (copy, do not edit; ask Jayed to regenerate when contracts change).
3. **Layout**: sidebar with steps Upload, Dataset, Training, Models, Rules, Review, Export; `WorkflowContext` stores ids.
4. **Upload page**: six file inputs plus format selector; shows `DatasetValidationResponse` issues in a table (errors red, warnings amber).
5. **Dataset preview page**: summary cards from `DatasetSummary`; authorisation density from `RBACAuthorisationResponse`; Recharts bar charts of attribute counts if data is provided.
6. **Training config page**: form built from `TrainingConfigRequest` (models, test size, CV folds, seed, negative sampling, F1 target, min support/confidence). Submit shows a progress state; poll or await response.
7. **Model comparison page**: table and bar chart of precision, recall, F1, training time; badge "used for rule extraction" on the Decision Tree.
8. **Metrics page**: cards for precision, recall, F1, OPR, UPR, rule count, WSC from `PolicyMetrics`; label "evaluated on full access matrix".
9. **Rules page**: each rule rendered as readable text (for example "PERMIT read IF user.department == Finance AND resource.sensitivity in [low, medium]") with support, confidence and status.
10. **Review page**: per-rule Approve / Reject / Edit buttons (edit changes conditions, sends `RuleDecision` with `edited_conditions`). Submit builds an `ApprovalRequest`. No "approve all" default.
11. **Export page**: format selector (json/xacml), preview of `ExportResponse.content`, download button. Disabled until `n_approved > 0`.
12. **Polish**: loading, empty and error states using `ErrorResponse.message`; responsive layout.
13. **Integration**: set `VITE_USE_MOCKS=false`, `VITE_API_BASE_URL=http://localhost:8000/api/v1`, fix mismatches by reporting to Jayed (never by changing contracts).

## 5. Required files and functions

```
src/services/api.js         uploadDataset, getAuthorisation, runTraining, getComparison, getRules,
                            optimisePolicy, getValidation, submitReview, exportPolicy
src/services/mockApi.js     same function names returning mock JSON after a short delay
src/context/WorkflowContext.jsx
src/layouts/AppLayout.jsx
src/pages/UploadPage.jsx, DatasetPage.jsx, TrainingPage.jsx, ModelsPage.jsx,
          RulesPage.jsx, ReviewPage.jsx, MetricsPage.jsx, ExportPage.jsx
src/components/RuleCard.jsx, MetricCard.jsx, IssueTable.jsx, FileDropzone.jsx, ErrorBanner.jsx
src/utils/formatRule.js     contract rule -> readable string
```

## 6. Input and output contracts

Field names are exactly those in `shared/schemas/contracts.py`; examples in `shared/sample_responses/*.json`. Endpoint list: `PROJECT_RULES.json` under `api_standards.endpoints`. All JSON fields are `snake_case`; keep them as-is in JS (do not rename to camelCase).

## 7. Dependencies

Mocks first (`shared/sample_responses`). Later the live backend from Jayed. Nothing else.

## 8. Installation

```bash
cd frontend
npm install
cp .env.example .env     # create .env.example with the two variables below
```

```
VITE_USE_MOCKS=true
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 9. Commands

```bash
npm run dev       # development server
npm run build     # production build (used by CI)
npm run lint      # if ESLint is configured
```

## 10. Testing instructions

- `npm run build` must pass.
- Manually walk the whole flow in mock mode and record it in `frontend/README.md` as a checklist.
- Optional: Vitest tests for `formatRule.js` and for the approval-request builder.
- Test each page with: normal data, empty data, and the `error_response.json` mock.

## 11. Integration instructions

1. Start in mock mode; do not wait for the backend.
2. When Jayed announces an endpoint is live, switch only that call to the real API.
3. If a field is missing or different, open an issue tagged `contract` for Jayed; do not patch around it silently.

## 12. Restrictions

- Do not implement ML, rule optimisation, metric calculation or export formatting in the UI.
- Do not edit `backend/`, `policy_engine/`, `shared/`, or `tests/`.
- No auto-approval. The Export page offers only approved rules.
- No new UI frameworks beyond the approved stack.

## 13. Completion criteria

- All eight pages work in mock mode and against the live backend.
- The demo flow (upload, train, review rules, approve, export) works end to end.
- `npm run build` passes; `frontend/README.md` documents setup and the manual test checklist.

## 14. Common mistakes to avoid

- Calling `fetch` inside components instead of `src/services/`.
- Editing mock JSON to make the UI look nicer (mocks must match contracts).
- Computing metrics client-side.
- Enabling export before any approval.
- Waiting for the backend before starting.
