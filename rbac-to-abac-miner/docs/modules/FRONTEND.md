# Module: Frontend

**Owner:** Naeem (`frontend/`). Stack: React.js, Vite, Tailwind CSS, `react-router-dom`, Recharts. Plain JavaScript (JSX).
The UI renders what the API returns. It contains **no** ML, rule-optimisation, metric or export logic.

## 1. Setup

```bash
cd frontend
npm create vite@latest . -- --template react     # choose "Ignore files and continue" if asked
npm install react-router-dom recharts
npm install tailwindcss @tailwindcss/vite        # Tailwind CSS v4: add the plugin in vite.config.js
npm install -D vitest @testing-library/react jsdom
```

`vite.config.js`: `import tailwindcss from '@tailwindcss/vite'` and `plugins: [react(), tailwindcss()]`. In `src/index.css`: `@import "tailwindcss";`.
`.env` (copy from `.env.example`): `VITE_USE_MOCKS=true`, `VITE_API_BASE_URL=http://localhost:8000/api/v1`.

## 2. Structure

```
frontend/src/
  services/   api.js, mockApi.js, mocks/        (the only place that does HTTP or loads mocks)
  context/    WorkflowContext.jsx                (dataset_id, run_id, policy_id, last responses)
  layouts/    AppLayout.jsx                      (sidebar + header)
  pages/      UploadPage, DatasetPage, TrainingPage, ModelsPage, RulesPage, ReviewPage, MetricsPage, ExportPage
  components/ RuleCard, MetricCard, IssueTable, FileDropzone, ErrorBanner
  hooks/      useApi, useUpload, useRun
  utils/      formatRule.js
```

## 3. Routes and the API calls behind them

| Route | Page | Service function | Endpoint | Response model |
|---|---|---|---|---|
| `/upload` | UploadPage | `uploadDataset(formData)` | POST `/datasets/upload` | `DatasetValidationResponse` |
| `/dataset` | DatasetPage | `getAuthorisation(datasetId)` | GET `/datasets/{id}/authorisation` | `RBACAuthorisationResponse` |
| `/training` | TrainingPage | `runTraining(config)` | POST `/training/run` | `TrainingResponse` |
| `/models` | ModelsPage | `getComparison(runId)` | GET `/training/{id}/comparison` | `ModelComparisonResponse` |
| `/rules` | RulesPage | `getRules(runId)`, `optimisePolicy(runId)` | GET `/training/{id}/rules`, POST `/policies/optimise/{id}` | `ExtractedRulesResponse`, `OptimisedPolicyResponse` |
| `/metrics` | MetricsPage | `getValidation(policyId)` | GET `/policies/{id}/validation` | `PolicyValidationResponse` |
| `/review` | ReviewPage | `submitReview(request)` | POST `/policies/{id}/review` | `ApprovalResponse` |
| `/export` | ExportPage | `exportPolicy(request)` | POST `/policies/{id}/export` | `ExportResponse` |

`mockApi.js` exports the same function names and resolves the matching copy of `shared/sample_responses/*.json` after a 300 to 600 ms delay. `api.js` chooses between the two with `import.meta.env.VITE_USE_MOCKS === 'true'`. Mock files are **copied, never edited**; if a mock looks wrong, report a contract issue to Jayed.

## 4. Display rules

- Field names stay `snake_case` end to end.
- Rule text from `formatRule(rule)`: `PERMIT <action> IF user.department == Finance AND resource.sensitivity in [low, medium]`. Operators are shown as in the contract (`==`, `!=`, `in`, `not_in`, `<=`, `<`, `>`, `>=`).
- Status chips: `candidate` grey, `optimised` blue, `approved` green, `rejected` red, `edited` amber ("needs re-validation").
- Policy metrics cards: Precision, Recall, F1, OPR, UPR, Rule count, WSC, with the caption "evaluated on full access matrix". Model comparison uses a separate page and caption "evaluated on held-out test split". Never mix them.
- Model comparison: the Decision Tree row carries a badge "used for rule extraction" (`selected_for_extraction`). Show whether `f1_target_met`.
- Validation issues: errors red, warnings amber, grouped by `file`.
- Review page: every rule starts unreviewed; there is **no** "approve all" shortcut or default. Edit opens a conditions editor that produces `edited_conditions`.
- Export page: format selector, preview of `content`, download button (`.json` or `.xml`). Disabled until the latest `ApprovalResponse.n_approved > 0`.
- Every page has loading, empty and error states; errors show `ErrorResponse.message`.

## 5. Quality gates

- `npm run build` passes (CI runs it when `frontend/package.json` exists).
- Vitest: `formatRule`, the `ApprovalRequest` builder, and the mock/real switch.
- Manual checklist in `frontend/README.md` walked through in mock mode, in live mode, and with `error_response.json`.
