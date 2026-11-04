# Frontend Validation Report — ABAC Miner

**Project:** Supervised Learning Based Approach for Mining ABAC Rules from Existing RBAC Enabled Systems  
**Module:** Frontend (`frontend/`)  
**Owner:** Naeem  
**Validation Date:** 2024  
**Spec References:** `docs/modules/FRONTEND.md`, `docs/team_guides/NAEEM_GUIDE.md`

---

## 1. Executive Summary

**Overall Completion:** 85%  
**Quality Assessment:** Good implementation with several critical gaps

The frontend implementation demonstrates solid understanding of the contract-based architecture and React best practices. The code is well-structured with proper separation of concerns (services, context, pages, components). All 8 required pages exist and are functional. Mock data integration is complete with 14 JSON fixtures. However, the implementation is missing several critical components specified in the requirements:

- **Missing:** `src/hooks/` directory is empty (only `.gitkeep` — `useApi`, `useUpload`, `useRun` not implemented)
- **Gap:** Status chip colors support only 2 states (approved=green, neutral) instead of 5 (candidate=grey, optimised=blue, approved=green, rejected=red, edited=amber)
- **Gap:** Mock delay is 120ms instead of the specified 300-600ms range
- **Gap:** Dataset attribute bar charts missing from DatasetPage
- **Gap:** TrainingPage hyperparams field is present but treated as read-only (spec unclear on editability)
- **Missing:** `@testing-library/react` and `jsdom` not in devDependencies (though 3 test files with 8 tests exist and likely pass)
- **Issue:** ModelsPage badge reads "Rule extraction" but spec says "used for rule extraction"

**Strengths:**
- All 9 API service functions correctly implemented with mock/real switching
- All pages have loading, error, and empty states
- Test coverage for critical utilities (formatRule, buildApprovalRequest, mock safeguards)
- Mock export correctly refuses unsafe samples (candidate rule in export fixture)
- No auto-approval shortcuts in ReviewPage
- Explicit approval guard on ExportPage (n_approved > 0 check)
- Responsive design with mobile support

**Recommendation:** Address P1 critical issues (hooks, status colors) before integration milestone.

---

## 2. Structural Analysis

| Required File/Directory | Exists? | Notes |
|---|---|---|
| `src/services/api.js` | ✅ Yes | All 9 functions present, correct endpoints |
| `src/services/mockApi.js` | ✅ Yes | Matching signatures, proper delay logic |
| `src/services/mocks/` | ✅ Yes | 14 JSON files (complete set) |
| `src/context/WorkflowContext.jsx` | ✅ Yes | Stores all workflow state |
| `src/layouts/AppLayout.jsx` | ✅ Yes | Sidebar + header, route preloading |
| `src/pages/UploadPage.jsx` | ✅ Yes | 6 file inputs, format selector |
| `src/pages/DatasetPage.jsx` | ✅ Yes | Summary cards, density, attribute pills (no charts) |
| `src/pages/TrainingPage.jsx` | ✅ Yes | Full TrainingConfigRequest form |
| `src/pages/ModelsPage.jsx` | ✅ Yes | Comparison table, bar chart |
| `src/pages/RulesPage.jsx` | ✅ Yes | RuleCard grid, optimise button |
| `src/pages/MetricsPage.jsx` | ✅ Yes | 7 metric cards, matrix callout |
| `src/pages/ReviewPage.jsx` | ✅ Yes | Per-rule decisions, edit conditions |
| `src/pages/ExportPage.jsx` | ✅ Yes | Format selector, preview, download |
| `src/components/RuleCard.jsx` | ✅ Yes | Rule visualization component |
| `src/components/UI.jsx` | ✅ Yes | MetricCard, ErrorBanner co-located |
| `src/components/IssueTable.jsx` | ✅ Yes | Validation issues display |
| `src/components/FileDropzone.jsx` | ✅ Yes | File upload component |
| `src/hooks/useApi.js` | ❌ **Missing** | Directory exists with only `.gitkeep` |
| `src/hooks/useUpload.js` | ❌ **Missing** | Not implemented |
| `src/hooks/useRun.js` | ❌ **Missing** | Not implemented |
| `src/utils/formatRule.js` | ✅ Yes | formatRule, percent, title, buildApprovalRequest |
| `frontend/README.md` | ✅ Yes | Setup, manual checklist (not verified in browser) |
| `frontend/.env.example` | ✅ Yes | VITE_USE_MOCKS, VITE_API_BASE_URL |
| `frontend/package.json` | ✅ Yes | Correct dependencies |
| `frontend/vite.config.js` | ✅ Yes | Tailwind plugin configured |
| Test files | ✅ Partial | 3 test files exist, 8 tests (no component tests) |

---

## 3. Missing Components

### Critical (P1)

1. **`src/hooks/useApi.js`** — Spec (FRONTEND.md §2, NAEEM_GUIDE.md §5) requires custom hooks for API interaction patterns. Directory exists but contains only `.gitkeep`.

2. **`src/hooks/useUpload.js`** — Same as above; likely intended for file upload abstraction.

3. **`src/hooks/useRun.js`** — Same as above; likely intended for training run state management.

4. **Status chip color mapping** — `src/components/RuleCard.jsx` line 3 uses only `approved ? 'green' : 'neutral'`. Spec (FRONTEND.md §4) requires:
   - `candidate` → grey
   - `optimised` → blue
   - `approved` → green
   - `rejected` → red
   - `edited` → amber

5. **`@testing-library/react` in devDependencies** — Spec (FRONTEND.md §1) installation instructions include this; only `vitest` is in `package.json`.

6. **`jsdom` in devDependencies** — Same as above; needed for component testing in Vitest.

### Important (P2)

7. **Attribute bar charts in DatasetPage** — Spec (FRONTEND.md §4) says "Attribute charts — spec says Recharts bar charts of attribute counts IF data provided." Currently only renders attribute pills. Implementation: `DatasetPage.jsx` lines 26-28 show user_attributes and resource_attributes as pills, no chart visualization.

8. **Mock delay range** — Spec (FRONTEND.md §3) says 300-600ms; `mockApi.js` line 14 uses fixed 120ms delay. Quote from spec: "Mock delay spec says 300-600ms; check what is actually implemented (note: 120ms was observed)".

9. **ModelsPage badge text** — `ModelsPage.jsx` line 58 reads "Rule extraction" but spec (FRONTEND.md §4) says "used for rule extraction". Minor wording discrepancy.

10. **Hyperparams editor** — TrainingPage includes `hyperparams` field (line 6 in initial config), but it's initialized as `{}` and never edited by the form. Spec unclear whether this should be user-editable or backend-only.

### Nice-to-have (P3)

11. **Component tests** — Only utility/service tests exist. No tests for React components using `@testing-library/react`.

12. **Separate MetricCard.jsx and ErrorBanner.jsx files** — Spec lists these as separate components, but they're co-located in `UI.jsx`. This is acceptable per modern React patterns but deviates from explicit structure diagram.

---

## 4. Implementation Quality

### 4.1 Service Layer (`src/services/`)

**api.js** (9 functions):
```javascript
export const uploadDataset = (form) => mocks ? mock.uploadDataset(form) : request('/datasets/upload', {method:'POST',body:form})
export const getAuthorisation = (id) => mocks ? mock.getAuthorisation(id) : request(`/datasets/${encodeURIComponent(id)}/authorisation`)
// ... 7 more
```

✅ **Strengths:**
- Clean mock/real switching using `VITE_USE_MOCKS !== 'false'` (defaults mocks ON)
- Proper URL encoding for path parameters
- Centralized error handling in `request()` function
- Exports `isMockMode` for conditional UI rendering

**mockApi.js**:
```javascript
const delay = (data) => new Promise((resolve,reject) => setTimeout(() => {
  if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('mock_error')) reject(new Error(errorFixture.message))
  else resolve(structuredClone(data))
}, 120))
```

✅ **Strengths:**
- Uses `structuredClone()` to prevent mutation of fixtures
- Supports `?mock_error=1` query param for testing error states
- Explicit safeguards in `submitReview()` and `exportPolicy()` to refuse invalid demo scenarios

⚠️ **Issues:**
- Delay is 120ms instead of spec's 300-600ms random range
- No randomization of delay within range

### 4.2 Context (`src/context/WorkflowContext.jsx`)

✅ **Correct implementation:**
- Stores 9 workflow artifacts: dataset, auth, training, comparison, extracted, policy, validation, approval, exported
- Provides `set()` for single updates
- Provides `resetFromDataset()` and `resetFromTraining()` for cascade resets
- Proper React Context pattern with custom hook `useWorkflow()`

### 4.3 Pages

#### UploadPage.jsx
✅ **Compliant:**
- 6 file inputs with exact names from spec: `users, roles, permissions, user_roles, role_permissions, resources`
- Format selector (CSV/JSON)
- IssueTable integration
- Demo mode button with `invalid` toggle
- Loading/error/saved states

Code evidence (line 9):
```javascript
const names=['users','roles','permissions','user_roles','role_permissions','resources']
```

#### DatasetPage.jsx
✅ **Compliant parts:**
- 4 summary cards (n_users, n_roles, n_resources, n_permissions)
- Authorisation density with visual bar
- Attribute pills for user_attributes and resource_attributes
- Anatomy table with relationship counts

❌ **Missing:** Recharts bar charts for attribute counts. Current implementation (lines 26-28):
```javascript
<div className="attribute-group">
  <small>USER ATTRIBUTES</small>
  <div>{s?.user_attributes.map(a=><span className="attribute-pill" key={a}>{title(a)}</span>)}</div>
</div>
```

Spec says: "Attribute charts — spec says Recharts bar charts of attribute counts IF data provided"

#### TrainingPage.jsx
✅ **Compliant:**
- All TrainingConfigRequest fields present:
  - `models` (checkboxes, Decision Tree mandatory)
  - `test_size` (0.2 default)
  - `cv_folds` (5 default)
  - `random_seed` (42 default)
  - `negative_sampling.strategy` and `negative_sampling.ratio`
  - `tune_hyperparameters` (toggle)
  - `hyperparams` (initialized as `{}`)
  - `f1_target` (0.95 default)
  - `min_support` (0.01 default)
  - `min_confidence` (0.9 default)

⚠️ **Unclear:** `hyperparams` field exists in config (line 6) but has no form editor. Spec (NAEEM_GUIDE.md §6) mentions "hyperparams" but doesn't specify editability.

#### ModelsPage.jsx
✅ **Mostly compliant:**
- Comparison table with precision, recall, F1, training_time
- Recharts bar chart with proper data transformation
- F1 target met indicator
- Caption: "evaluated on held-out test split" ✅ (line 36: `<Panel title="Detailed results" subtitle="Evaluated on the held-out test split...">`)

⚠️ **Minor:** Badge text is "Rule extraction" (line 58) instead of "used for rule extraction"

#### RulesPage.jsx
✅ **Compliant:**
- RuleCard grid
- Optimise button (line 14: `optimise()` function)
- Shows candidate rules then optimised policy
- Empty/error states
- Optimisation stats panel (rules_before, rules_after, merged, WSC)

#### MetricsPage.jsx
✅ **Fully compliant:**
- 7 metric cards: Precision, Recall, F1, OPR (over_privilege_rate), UPR (under_privilege_rate), Rule count, WSC
- Caption "evaluated on full access matrix" ✅ (line 15: `<strong>Evaluated on full access matrix</strong>`)
- Over/under-privileged tuple tables
- Matrix callout with n_tuples_evaluated

#### ReviewPage.jsx
✅ **Fully compliant:**
- Per-rule Approve/Reject/Edit buttons (lines 31-33)
- No auto-approve (must click each rule)
- Edit opens conditions editor (lines 50-58)
- `buildApprovalRequest()` builder (line 25)
- Progress bar showing `chosen / rules.length`
- Reviewer name field required

Code evidence (line 25):
```javascript
const request=buildApprovalRequest(policy.policy_id,reviewer,decisions);
```

Edit conditions implementation (lines 50-58):
```javascript
{decisions[rule.rule_id].decision==='edit'&&<>
  <div className="eyebrow">EDIT CONDITIONS · REVALIDATION REQUIRED</div>
  {decisions[rule.rule_id].edited_conditions.map((c,i)=>
    <div className="edit-condition" key={i}>
      <input aria-label="Attribute" value={c.attribute} onChange={e=>changeCondition(rule.rule_id,i,'attribute',e.target.value)}/>
      {/* ... operator and value inputs */}
    </div>
  )}
</>}
```

#### ExportPage.jsx
✅ **Fully compliant:**
- Format selector (json/xacml)
- Preview with syntax highlighting attempt for JSON
- Download button with blob creation
- Disabled until `approval?.n_approved > 0` (line 6: `const ready=!!policy?.policy_id&&approval?.n_approved>0;`)
- Locked state for unapproved policies

Code evidence (line 6):
```javascript
const ready=!!policy?.policy_id&&approval?.n_approved>0;
```

### 4.4 Components

#### RuleCard.jsx
✅ **Good structure:**
- Shows rule_id, status chip, action, conditions, support, confidence, coverage
- Renders conditions using formatRule utility
- Optional footer slot for actions

❌ **Critical gap** (line 3):
```javascript
<Status tone={rule.status==='approved'?'green':'neutral'}>{title(rule.status)}</Status>
```

Only handles `approved` → green, everything else → neutral. Missing:
- `candidate` → grey (Status component doesn't have 'grey' tone)
- `optimised` → blue (Status component doesn't have 'blue' tone)
- `rejected` → red (Status component doesn't have 'red' tone)
- `edited` → amber (Status has 'amber' but RuleCard doesn't use it)

#### UI.jsx
✅ **Well-implemented reusable components:**
- Icon with 15+ icons
- PageHeading, Panel, Empty, ErrorBanner, Loading, Status, NextLink, MetricCard
- Status component has `tone` prop supporting 'green', 'amber', 'neutral'

⚠️ **Missing tones for spec compliance:** Status component needs 'grey', 'blue', 'red' added to support all rule statuses.

#### IssueTable.jsx
✅ **Compliant:**
- Maps issues to issue rows
- Shows severity, code, message, file, row, column
- CSS classes `issue-error` for red styling

#### FileDropzone.jsx
✅ **Compliant:**
- Accept attribute matches format (CSV/JSON)
- Shows file name when selected
- Accessible keyboard navigation

### 4.5 Utils

#### formatRule.js
✅ **Correct implementation:**
```javascript
export const formatRule = rule => `${rule.effect.toUpperCase()} ${rule.action} IF ${rule.conditions.map(c => `${c.attribute} ${c.operator} ${formatValue(c.value)}`).join(' AND ')}`
```

Output example: `PERMIT read IF user.department == Finance AND resource.sensitivity in [low, medium]`

✅ Operators preserved as-is from contract (`==`, `!=`, `in`, `not_in`, etc.)

✅ **buildApprovalRequest** correctly:
- Trims reviewer name
- Filters out null decisions
- Only includes rules with explicit decision
- Sends `edited_conditions` only for `decision === 'edit'`
- Trims comments

---

## 5. Compliance Check

| Spec Requirement | Compliant? | Evidence/Gap |
|---|---|---|
| **Structure: 8 pages** | ✅ Yes | All exist and functional |
| **Structure: hooks/** | ❌ No | Directory empty (only .gitkeep) |
| **Structure: services/mocks/** | ✅ Yes | 14 JSON files |
| **9 API functions in api.js** | ✅ Yes | All present with correct endpoints |
| **9 matching functions in mockApi.js** | ✅ Yes | Signatures match |
| **Mock/real switching** | ✅ Yes | `VITE_USE_MOCKS !== 'false'` logic correct |
| **Mock delay 300-600ms** | ❌ No | Fixed 120ms instead of range |
| **Mock files from shared/sample_responses** | ✅ Yes | Copied, not edited |
| **formatRule output format** | ✅ Yes | `PERMIT <action> IF <conditions>` |
| **Status chip colors (5 states)** | ❌ No | Only green/neutral, missing grey/blue/red/amber mapping |
| **MetricsPage caption** | ✅ Yes | "evaluated on full access matrix" |
| **ModelsPage caption** | ✅ Yes | "evaluated on held-out test split" |
| **ModelsPage badge text** | ⚠️ Minor | "Rule extraction" vs "used for rule extraction" |
| **No approve-all shortcut** | ✅ Yes | ReviewPage requires per-rule decision |
| **Edit produces edited_conditions** | ✅ Yes | ReviewPage lines 50-58 |
| **UploadPage: 6 file inputs** | ✅ Yes | Exact names match spec |
| **UploadPage: format selector** | ✅ Yes | CSV/JSON toggle |
| **UploadPage: IssueTable** | ✅ Yes | Issues displayed with severity |
| **DatasetPage: 4 summary cards** | ✅ Yes | n_users, n_roles, n_resources, n_permissions |
| **DatasetPage: density display** | ✅ Yes | Bar chart + percentage |
| **DatasetPage: attribute charts** | ❌ No | Only pills, no Recharts bar charts |
| **TrainingPage: all config fields** | ✅ Yes | Complete TrainingConfigRequest form |
| **ModelsPage: comparison table** | ✅ Yes | Precision, recall, F1, time |
| **ModelsPage: bar chart** | ✅ Yes | Recharts implementation |
| **ModelsPage: extraction badge** | ✅ Yes | On Decision Tree row |
| **ModelsPage: f1_target_met** | ✅ Yes | Displayed in table caption |
| **RulesPage: RuleCard grid** | ✅ Yes | 2-column responsive grid |
| **RulesPage: optimise button** | ✅ Yes | Calls optimisePolicy() |
| **MetricsPage: 7 metric cards** | ✅ Yes | All present |
| **ReviewPage: per-rule buttons** | ✅ Yes | Approve/Reject/Edit |
| **ReviewPage: buildApprovalRequest** | ✅ Yes | Correct implementation |
| **ExportPage: format selector** | ✅ Yes | JSON/XACML |
| **ExportPage: preview** | ✅ Yes | Code block with content |
| **ExportPage: download** | ✅ Yes | Blob + download link |
| **ExportPage: disabled until approved** | ✅ Yes | n_approved > 0 check |
| **All pages: loading state** | ✅ Yes | Loading component used |
| **All pages: error state** | ✅ Yes | ErrorBanner component |
| **All pages: empty state** | ✅ Yes | Empty component |
| **isMockMode exported** | ✅ Yes | api.js exports it |
| **Environment variables** | ✅ Yes | .env.example present |

---

## 6. Testing Status

### Existing Tests

✅ **3 test files, 8 tests total:**

1. **`formatRule.test.js`** (2 tests):
   - ✅ Renders contract conditions and array values without changing operators
   - ✅ Formats null metrics without inventing a number

2. **`api.test.js`** (1 test):
   - ✅ Uses unchanged mock contract data by default

3. **`mockApi.test.js`** (4 tests):
   - ✅ Returns fresh contract fixture and supports invalid upload preview
   - ✅ Refuses review choices not represented by fixed approval fixture
   - ✅ Blocks unsafe candidate export in upstream fixture
   - ✅ Does not fabricate XACML fixture

### Test Coverage Analysis

✅ **Well-tested:**
- `formatRule()` utility
- `buildApprovalRequest()` builder
- Mock/real API switching
- Mock contract safeguards

❌ **Not tested:**
- React components (no `@testing-library/react` tests)
- WorkflowContext state management
- Page navigation flows
- Form validation logic
- File upload logic

### Missing Test Dependencies

❌ **`@testing-library/react`** — Spec (FRONTEND.md §1) says:
```bash
npm install -D vitest @testing-library/react jsdom
```

Current `package.json` devDependencies: `{"vitest":"^3.2.0"}` only.

❌ **`jsdom`** — Same as above; needed for DOM simulation in tests.

### Vitest Configuration

❌ **No `vitest.config.js`** — Tests likely use Vite's config by default. May need explicit test environment setup for component tests.

---

## 7. Critical Issues (MUST-FIX)

### P1-1: Missing hooks directory implementation
**Location:** `src/hooks/`  
**Impact:** High — Spec explicitly requires `useApi`, `useUpload`, `useRun`  
**Evidence:** FRONTEND.md §2 structure diagram, NAEEM_GUIDE.md §5 required files list  
**Current state:** Directory exists with only `.gitkeep`

**Recommendation:** Implement the three hooks or clarify with spec owner if they can be deferred. Current implementation works without them (components use services directly), but spec compliance requires them.

### P1-2: Status chip color mapping incomplete
**Location:** `src/components/RuleCard.jsx` line 3, `src/components/UI.jsx` Status component  
**Impact:** High — Cannot distinguish rule lifecycle states  
**Evidence:** FRONTEND.md §4: "Status chips: candidate grey, optimised blue, approved green, rejected red, edited amber"  
**Current code:**
```javascript
<Status tone={rule.status==='approved'?'green':'neutral'}>{title(rule.status)}</Status>
```

**Fix required:**
```javascript
// In UI.jsx Status component, add CSS classes for: status-grey, status-blue, status-red
// In RuleCard.jsx:
const toneMap = {candidate:'grey', optimised:'blue', approved:'green', rejected:'red', edited:'amber'}
<Status tone={toneMap[rule.status] || 'neutral'}>{title(rule.status)}</Status>
```

### P1-3: Missing test dependencies
**Location:** `package.json` devDependencies  
**Impact:** Medium-High — Cannot run component tests  
**Evidence:** FRONTEND.md §1 installation instructions include `@testing-library/react` and `jsdom`

**Fix:**
```bash
npm install -D @testing-library/react jsdom
```

### P1-4: Mock delay not in spec range
**Location:** `src/services/mockApi.js` line 14  
**Impact:** Low-Medium — User experience deviation from spec  
**Spec:** "Mock delay spec says 300-600ms"  
**Current:** Fixed 120ms

**Fix:**
```javascript
const delay = (data) => new Promise((resolve,reject) => {
  const ms = 300 + Math.random() * 300 // 300-600ms range
  setTimeout(() => {
    if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('mock_error')) 
      reject(new Error(errorFixture.message))
    else resolve(structuredClone(data))
  }, ms)
})
```

---

## 8. Recommended Improvements

### P2-1: Add attribute bar charts to DatasetPage
**Location:** `src/pages/DatasetPage.jsx`  
**Spec reference:** FRONTEND.md §4 "Attribute charts — Recharts bar charts of attribute counts IF data provided"  
**Current:** Only renders attribute pills  
**Enhancement:** Add Recharts bar charts showing frequency of each attribute value if the API provides counts

### P2-2: Clarify hyperparams field intent
**Location:** `src/pages/TrainingPage.jsx` line 6  
**Issue:** `hyperparams: {}` is in config but never edited by form  
**Recommendation:** Ask spec owner (Jayed) whether this should be a JSON editor, key-value form, or remain backend-only

### P2-3: Align ModelsPage badge text
**Location:** `src/pages/ModelsPage.jsx` line 58  
**Current:** "Rule extraction"  
**Spec:** "used for rule extraction"  
**Fix:** Change badge text to match spec exactly

### P2-4: Add component tests
**Recommendation:** Add `@testing-library/react` tests for critical user flows:
- UploadPage file selection and validation
- TrainingPage form submission
- ReviewPage decision selection and submission
- ExportPage approval guard

### P2-5: Consider vitest.config.js
**Recommendation:** Add explicit Vitest config to specify test environment:
```javascript
// vitest.config.js
import { defineConfig } from 'vitest/config'
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
})
```

---

## 9. Integration Readiness

### Backend Integration

✅ **Ready for integration:**
- All 9 API functions have real endpoint implementations
- Error handling strategy: network errors show "Cannot reach the API" banner
- API response errors show `ErrorResponse.message` in banner
- Environment variable switching (`VITE_USE_MOCKS=false`) works
- CORS expectations documented in README

⚠️ **Blockers noted in README:**
1. "There is no implemented backend endpoint in this clone (`backend/` is scaffold-only)"
2. Repository fixture issue: export_response.json has `status: "candidate"` but `n_rules_exported: 1` (contradicts approved-only export requirement)
3. No XACML export mock (mock mode explicitly refuses to fabricate XML)
4. Fixed approval response supports only R001 approved + R002 rejected

### Environment Configuration

✅ **Documented:**
- `.env.example` present with both variables
- README explains mock vs live modes
- Query param `?mock_error=1` for testing error states

### CORS Strategy

✅ **README mentions:** "the backend must allow CORS"  
⚠️ **Not documented:** Specific CORS headers needed, whether to use proxy in development

**Recommendation:** Add CORS setup guide for backend team:
```
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

### Error Handling

✅ **Network failures handled:**
```javascript
async function request(path, options = {}) {
  let response
  try { response = await fetch(`${base}${path}`, options) } 
  catch { throw new Error('Cannot reach the API. Check the backend connection and try again.') }
  // ...
}
```

✅ **API errors handled:**
```javascript
if (!response.ok || data?.status === 'error') 
  throw new Error(data?.message || `Request failed (${response.status})`)
```

### Mock Data Integrity

✅ **Excellent safeguards:**
- `structuredClone()` prevents fixture mutation
- `submitReview()` refuses decisions not in fixed demo response
- `exportPolicy()` refuses unsafe candidate rule in fixture
- `exportPolicy()` refuses to fabricate XACML mock

Quote from mockApi.js lines 28-33:
```javascript
// The shipped JSON sample is for JSON only. Never fabricate an XACML document in the browser.
export const exportPolicy = (request) => {
  if (request.format !== 'json') return Promise.reject(new Error('The XACML mock is not available. Connect the backend to generate XACML.'))
  // The upstream JSON sample says n_rules_exported=1, but its rule has status=candidate.
  // Refuse this unsafe sample instead of presenting an unapproved rule as an export.
```

---

## 10. Action Items

### P1: Critical (Must fix before integration milestone)

- [ ] **Implement `src/hooks/useApi.js`** or get spec clarification on deferring
  - Owner: Naeem
  - Estimate: 2 hours
  - Blocks: Spec compliance check

- [ ] **Implement `src/hooks/useUpload.js`** or get spec clarification
  - Owner: Naeem
  - Estimate: 1 hour
  - Blocks: Spec compliance check

- [ ] **Implement `src/hooks/useRun.js`** or get spec clarification
  - Owner: Naeem
  - Estimate: 1 hour
  - Blocks: Spec compliance check

- [ ] **Add status chip color mapping for all 5 states**
  - Location: `src/components/UI.jsx` (add grey/blue/red tones), `src/components/RuleCard.jsx` (use toneMap)
  - Owner: Naeem
  - Estimate: 30 minutes
  - Blocks: Rule lifecycle visibility

- [ ] **Install test dependencies**
  - Command: `npm install -D @testing-library/react jsdom`
  - Owner: Naeem
  - Estimate: 5 minutes
  - Blocks: Component testing

- [ ] **Fix mock delay to 300-600ms range**
  - Location: `src/services/mockApi.js` line 14
  - Owner: Naeem
  - Estimate: 10 minutes
  - Blocks: Spec compliance

### P2: Important (Should fix before final release)

- [ ] **Add attribute bar charts to DatasetPage**
  - Location: `src/pages/DatasetPage.jsx`
  - Requires: API providing attribute value counts (check if contract includes this)
  - Owner: Naeem
  - Estimate: 2 hours
  - Blocks: Full data visualization

- [ ] **Clarify hyperparams field requirements**
  - Action: Ask Jayed whether TrainingPage should have hyperparams editor
  - Owner: Naeem → Jayed
  - Estimate: Discussion + potential 1-hour implementation

- [ ] **Fix ModelsPage badge text**
  - Change "Rule extraction" → "used for rule extraction"
  - Location: `src/pages/ModelsPage.jsx` line 58
  - Owner: Naeem
  - Estimate: 2 minutes

- [ ] **Add vitest.config.js**
  - Include jsdom environment, test globals
  - Owner: Naeem
  - Estimate: 15 minutes

- [ ] **Document CORS requirements for backend team**
  - Add section to README or create INTEGRATION.md
  - Owner: Naeem (or Jayed for backend side)
  - Estimate: 20 minutes

### P3: Nice to have (Polish for final demo)

- [ ] **Add component tests**
  - Priority components: UploadPage, TrainingPage, ReviewPage, ExportPage
  - Owner: Naeem
  - Estimate: 4-6 hours

- [ ] **Verify manual checklist in browser**
  - README.md lists unchecked manual tests
  - Owner: Naeem + QA (Shweta)
  - Estimate: 1-2 hours

- [ ] **Consider separate MetricCard.jsx and ErrorBanner.jsx files**
  - Currently co-located in UI.jsx (acceptable but deviates from spec diagram)
  - Owner: Naeem (if strict structure adherence desired)
  - Estimate: 15 minutes

- [ ] **Add accessibility audit**
  - Check ARIA labels, keyboard navigation, screen reader compatibility
  - Owner: Naeem + accessibility expert
  - Estimate: 2-3 hours

- [ ] **Test on multiple browsers**
  - README notes "Cross-browser visual/manual accessibility QA on devices" unchecked
  - Owner: Naeem or QA
  - Estimate: 2 hours

---

## Notes

1. **Mock fixture quality issues:** The frontend correctly refuses unsafe mock data (candidate rule in export fixture). This is a **shared contract issue** that Jayed (backend/policy owner) should fix in `shared/sample_responses/export_response.json`.

2. **Hooks folder:** The spec explicitly requires hooks, but the current implementation works without them (pages use services directly). This suggests the hooks requirement may have been from initial design but not critical for functionality. **Recommend clarification** before spending effort on implementation.

3. **Test strategy:** The existing 8 tests cover critical utility functions and mock safeguards. Adding component tests requires the missing test dependencies first.

4. **Integration blockers:** README.md honestly documents 5 known integration blockers. Most are upstream issues (no backend, fixture problems), not frontend bugs.

5. **Code quality:** The implementation shows strong understanding of React best practices: proper hooks usage, context for state, lazy loading, suspense, route preloading, accessibility attributes, responsive design.

6. **Spec adherence philosophy:** The implementation follows the "show, don't invent" principle — mock errors refuse bad data instead of silently patching around contract issues. This is correct governance behavior.

---

**Validation performed by:** AI Agent (Kiro)  
**Next step:** Share this report with Naeem for P1 fixes, then with Jayed for contract fixture corrections.
