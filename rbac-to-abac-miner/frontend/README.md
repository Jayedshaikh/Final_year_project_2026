# ABAC Miner — RBAC → ABAC administrator workspace

Frontend for the final-year project **Supervised Learning Based Approach for Mining ABAC Rules from Existing RBAC Enabled Systems**. Built only inside `frontend/`, following the repository's shared API contracts. The visual system uses warm off-white, charcoal and forest green rather than blue/purple. Invented brand names and non-functional labels were removed.

## Run

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The default (`VITE_USE_MOCKS=true`) runs without a backend, using **unchanged copies** of `shared/sample_responses/*.json`. On Overview, choose **Load sample dataset** to enter the demo flow. To test real file upload, supply six CSV or JSON files and a dataset name.

To exercise an API error on a page in mock mode, add `?mock_error=1` to its URL and trigger its request. The banner uses the unchanged `error_response.json` message.

For live integration, create a local `.env` from `.env.example` and set `VITE_USE_MOCKS=false` plus `VITE_API_BASE_URL` to the API origin ending in `/api/v1`. The browser must be able to reach that origin and the backend must allow CORS. In a proxy/hosted setup, use a browser-reachable relative `/api/v1` URL; `localhost` on the browser will not reach a remote sandbox backend.

```bash
npm run build
npm test
```

## Product flow

Overview / Upload → Dataset → Training → Model comparison → Rule discovery & optimisation → Full-matrix validation → Explicit review → Export.

- The frontend never computes ML results or policy metrics. Precision, recall, F1, OPR, UPR, rule count and WSC come from responses as-is.
- Only the Decision Tree is marked for rule extraction. Other models are benchmarks.
- Every review choice is an explicit click; `buildApprovalRequest` sends only selected decisions. An edit sends contract-shaped `edited_conditions` and remains pending revalidation. No approve-all action exists.
- Export stays locked until the latest review response reports at least one approved rule.
- Views are responsive down to compact 320px screens, use touch-friendly controls and a scrollable mobile drawer, prefetch routes on navigation intent, route-split the heavy model chart, and present loading, empty and API error states. Mock request delay is 120ms; live latency depends on the backend.

## Known integration blockers from repository scaffold

1. There is no implemented backend endpoint in this clone (`backend/` is scaffold-only). Live API integration cannot be verified until Jayed supplies endpoints.
2. The unchanged `shared/sample_responses/export_response.json` reports `n_rules_exported: 1`, but the serialized rule inside `content` has `status: "candidate"`, contradicting the approved-only export requirement. **Mock export intentionally refuses this fixture** rather than downloading an unapproved policy. Policy/backend owners should correct the fixture through shared-contract approval. Live export uses the API response without client-side rewriting.
3. There is no XACML export mock. Mock mode reports this clearly rather than fabricating XML.
4. The fixed approval response represents exactly R001 approved and R002 rejected. Mock mode refuses other review combinations to avoid displaying false counts. Live API supports arbitrary contract-valid decisions.
5. Workflow state is in memory. Refreshing the browser starts a new frontend session; persistent IDs can be added after backend lifecycle/storage behavior is agreed.

## Verification status

Automated checks run: `npm run build`; `npm test` (8 passing tests); `python scripts/validate_governance.py` (passed). Dev server responded HTTP 200. The manual checks below are **not yet verified in a browser**.

- [ ] Mock: sample load → dataset stats and authorisation preview
- [ ] Mock: training form and model comparison view
- [ ] Mock: extracted and optimised rules; full matrix metrics view
- [ ] Mock: explicit review and approval guard
- [ ] Mock: locked export and unsafe sample rejection
- [ ] Mock: invalid upload and `?mock_error=1` error banner on routes
- [ ] Live backend end-to-end (backend not implemented in repository yet)
- [ ] Live XACML preview/download (backend not implemented)
- [ ] Cross-browser visual/manual accessibility QA on devices

The page scaffolding and palette are frontend-only implementation decisions. Per repo governance, ask the documentation owner to record new project-level decisions in `docs/development_rules/DECISIONS.md`; this frontend-only branch deliberately does not edit shared docs.
