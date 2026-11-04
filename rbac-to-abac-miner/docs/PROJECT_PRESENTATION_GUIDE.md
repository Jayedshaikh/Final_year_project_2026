# RBAC-to-ABAC Miner — Complete Presentation Guide

**Project:** Supervised Learning Based Approach for Mining ABAC Rules from Existing RBAC Enabled Systems
**Team:** Jayed Altaf Shaikh (ML Engineer & Backend Lead), Naeem Julfekar Shaikh (Frontend),
Shweta Suresh Kidile (Data Engineering & QA), Granthali Sandesh Mahajan (Policy Engine)
**Institution:** Department of Computer Engineering | SITRC, Nashik | Sandip Foundation

---

---

# PART 1 — BASIC QUESTIONS & ANSWERS

---

## Section A: Concept Questions

**Q1. What is RBAC?**

Role-Based Access Control. Users are assigned roles, and roles have permissions.
Example: A "Doctor" role can read patient records. Simple but hard to maintain
when an organisation grows because roles keep multiplying.

**Q2. What is ABAC?**

Attribute-Based Access Control. Access is decided based on user and resource
attributes. Example: "If user.department = radiology AND resource.sensitivity
= high → permit read." More flexible and expressive than RBAC.

**Q3. What problem does this project solve?**

Organisations already use RBAC but want to move to ABAC. Writing ABAC rules
manually is slow and error-prone. This project automatically mines ABAC rules
from an existing RBAC system using supervised machine learning — no manual
rule writing needed.

**Q4. What is rule mining?**

Automatically discovering patterns (rules) from data. Here we find patterns
like "users from finance with seniority > 3 years can read billing reports"
without writing them manually.

**Q5. Why use machine learning for this?**

Access control data has patterns hidden in it. ML models find those patterns
automatically. The Decision Tree is especially useful because its structure
directly translates into readable IF-THEN rules.

---

## Section B: ML Questions

**Q6. Which ML models do you use?**

Three models: Decision Tree, Random Forest, and Gradient Boosting.

**Q7. Why Decision Tree for rule extraction?**

Because a Decision Tree is interpretable. Each path from root to leaf is
literally an IF-THEN rule. Random Forest and Gradient Boosting are black
boxes — you cannot read rules from them directly.

**Q8. What do Random Forest and Gradient Boosting do?**

They are accuracy references only. We compare their F1 scores with the
Decision Tree to show DT is competitive in accuracy while being interpretable.

**Q9. What is cross-validation?**

A technique to evaluate the model honestly. We split training data into 5
parts, train on 4 and test on 1, repeat 5 times. This gives a reliable
average performance without touching the real test set.

**Q10. What is overfitting?**

When a model memorises training data but fails on new data. We prevent it
by using a separate held-out test set (20% of data) never used during
training or tuning.

**Q11. What is data leakage?**

When information from the test set accidentally influences the model.
We prevent it by fitting the encoder only on training data, never on test data.

**Q12. What is stratified split?**

A split that preserves the class ratio in both train and test sets. If 70%
of samples are authorised, both train and test sets will also be ~70% authorised.

---

## Section C: Dataset Questions

**Q13. What data does the system accept as input?**

Six files: users, roles, permissions, user_roles (who has which role),
role_permissions (which role can do what), and resources. CSV or JSON format.

**Q14. What is the authorisation matrix?**

A table of every possible (user, resource, permission) combination. Each
combination is marked 1 (authorised) or 0 (not authorised). For our hospital
dataset: 12 users × 8 resources × 3 permissions = 288 tuples total.

**Q15. What are positive and negative samples?**

- Positive samples (S+) = all authorised tuples (label = 1)
- Negative samples (S-) = sampled unauthorised tuples (label = 0)
Together they form the training dataset for the classifier.

**Q16. Why sample negatives instead of using all?**

Because unauthorised tuples far outnumber authorised ones. Using all would
create a severely imbalanced dataset. We sample an equal number (1:1 ratio).

**Q17. What is seed=42?**

A random seed that fixes all random operations so results are identical every
time you run the project. Same seed on any machine = same output.

---

## Section D: System Questions

**Q18. What is the tech stack?**

- Backend: Python 3.13, FastAPI, Pydantic v2
- ML: scikit-learn (DT, RF, GB), XGBoost, Pandas, NumPy
- Frontend: React.js, Vite, Tailwind CSS, Recharts
- Testing: Pytest (118 tests)
- Storage: CSV/JSON files, Git/GitHub

**Q19. What is an API and why do you use it?**

API (Application Programming Interface) is how the frontend and backend
communicate. The frontend sends a request, the backend processes it and
sends a JSON response. We use 9 REST API endpoints.

**Q20. What is Pydantic?**

A Python library for data validation. It ensures every request and response
has exactly the right fields and types. Wrong input returns an automatic error.

---

## Section E: Output Questions

**Q21. What does an ABAC rule look like?**

```
Rule R001:
  Effect:     PERMIT
  Action:     read
  Conditions:
    user.department  ==  "radiology"
    resource.sensitivity  ==  "high"
  Support:    0.352  (covers 35.2% of samples)
  Confidence: 1.000  (100% accurate)
```

**Q22. What is support and confidence?**

- Support = fraction of all samples this rule covers (0.352 = 35.2%)
- Confidence = of covered samples, how many are actually authorised (1.0 = 100%)

**Q23. What is OPR and UPR?**

- OPR (Over-Privilege Rate): system grants access when it should not (security risk)
- UPR (Under-Privilege Rate): system denies access when it should allow (usability issue)
Both are 0.000 in our demo run — meaning zero errors.

**Q24. What is the default decision?**

DENY. If no rule matches, access is denied. This is the safe fail-secure approach.
Never accidentally grant access on error.

**Q25. What is XACML?**

A standard XML format for access control policies. Our system exports approved
rules in XACML-style format for use in real enterprise systems.

**Q26. Who approves the rules?**

An administrator. The system never auto-approves anything. The admin reviews
each rule and explicitly approves, rejects, or edits it.

**Q27. What happens if you export before approving?**

HTTP 409 error — "No approved rules to export." Safety gate prevents
unapproved policies from being deployed.

**Q28. How many tests does the system have?**

118 automated tests — covering data pipeline, ML engine, all 9 API endpoints,
and contract validation. All 118 pass.

**Q29. How long does the full pipeline take?**

Under 1 second for the seed_hospital dataset. All 3 models trained, rules
extracted, optimised and exported in under 1 second on a standard laptop.

**Q30. Can this work with any organisation's RBAC data?**

Yes. Any organisation uploads their 6 RBAC tables in CSV or JSON and the
system mines ABAC rules automatically.

---

---

# PART 2 — PERFORMANCE EVALUATION TABLE

---

## Real Results — seed_hospital dataset, seed=42

| Parameter | Test Method | Target | Obtained | Status |
|---|---|---|---|---|
| Accuracy | Classification score on test set | ≥ 0.90 | **1.000** | Met |
| Precision | Precision score (positive class) | ≥ 0.90 | **1.000** | Met |
| Recall | Recall score (positive class) | ≥ 0.90 | **1.000** | Met |
| F1-score | F1 on held-out test split | ≥ 0.95 | **1.000** | Met |
| CV F1-score (mean) | 5-fold cross-validation | ≥ 0.95 | **1.000** | Met |
| Over-Privilege Rate | ABAC permits what RBAC denies | ≤ 0.05 | **0.000** | Met |
| Under-Privilege Rate | ABAC denies what RBAC allows | ≤ 0.10 | **0.000** | Met |
| Rule consistency | Conflict/redundancy checks | 0 conflicts | **0** | Met |
| Generation time | Training + extraction (all 3 models) | < 5 sec | **< 1 sec** | Met |
| Rules extracted | Count of candidate ABAC rules | ≥ 1 | **1 rule** | Met |
| Policy default decision | Fail-safe check | Always DENY | **DENY** | Met |
| Test cases passing | pytest automated suite | 100% | **118 / 118** | Met |

---

## Dataset Statistics

| Metric | Value |
|---|---|
| Users | 12 |
| Roles | 5 |
| Permissions | 3 (read, write, delete) |
| Resources | 8 |
| Total auth tuples | 288 |
| Authorised tuples (S+) | 200 |
| Unauthorised tuples | 88 |
| Auth density | 69.4% |
| Training samples | 230 |
| Test samples | 58 |

---

---

# PART 3 — HOW A NORMAL PERSON USES THE SYSTEM (UI Explanation)

---

## Simple Step-by-Step for a Non-Technical User

Imagine you are an IT manager at a hospital. You currently use a role-based
system. You want to upgrade to a smarter attribute-based system. Here is
exactly what you do:

---

### STEP 1 — Open the web application

Open your browser. Go to: http://localhost:5173 (or the hosted URL).
You see the RBAC-to-ABAC Miner dashboard.

---

### STEP 2 — Upload your data (Page: "Upload Dataset")

You see a form with 6 file upload boxes. Upload your 6 CSV files:

```
[ users.csv          ]  ← Your staff list with departments
[ roles.csv          ]  ← Your existing roles (Doctor, Analyst...)
[ permissions.csv    ]  ← What actions exist (read, write, delete)
[ user_roles.csv     ]  ← Who has which role
[ role_permissions.csv] ← Which role can do what
[ resources.csv      ]  ← Your files, records, systems
```

Click "Upload and Validate." The system checks for errors.

What you see:
- Green tick = valid dataset
- Summary: "12 users, 5 roles, 3 permissions, 8 resources"
- Any warnings shown (e.g. "Missing value in column clearance — imputed")

---

### STEP 3 — View the Access Matrix (Page: "Authorisation Matrix")

The system shows you a summary:
- Total combinations checked: 288
- Currently authorised: 200 (69.4%)
- Sample of who can access what

This confirms the system understood your existing RBAC setup correctly.

---

### STEP 4 — Train the Models (Page: "Train Models")

Click "Start Training." You can optionally adjust:
- Random seed (default: 42 for reproducibility)
- Negative sampling ratio (default: 1:1)
- F1 target (default: 0.95)

The system trains 3 models in under 1 second and shows a comparison table:

```
Model               F1 Score   Interpretable
─────────────────────────────────────────────
Decision Tree       1.000      YES ← used for rules
Random Forest       1.000      No
Gradient Boosting   1.000      No
```

The Decision Tree is automatically selected for rule extraction.

---

### STEP 5 — See Extracted Rules (Page: "Extracted Rules")

The system shows you the mined rules in plain language:

```
Rule R001
  Action:   read
  If user.department is "radiology" AND resource.sensitivity is "high"
  → PERMIT
  Support: 35.2% | Confidence: 100%
```

You can see exactly what the machine learned about your access patterns.

---

### STEP 6 — Optimise the Policy (Page: "Optimise Policy")

Click "Optimise." The system:
- Merges similar rules
- Removes redundant rules
- Shows before/after rule count and complexity score (WSC)

Then it validates the policy against ALL 288 tuples:
- Precision: 1.000 | Recall: 1.000 | F1: 1.000
- Over-privilege: 0% | Under-privilege: 0%

---

### STEP 7 — Review Rules as Admin (Page: "Review Policy")

For each rule you see three buttons:

```
Rule R001: user.department == radiology, resource.sensitivity == high → read
  [ APPROVE ]  [ REJECT ]  [ EDIT ]
```

- APPROVE → rule goes into the final policy
- REJECT → rule is discarded
- EDIT → you can modify conditions, then it needs re-validation

Nothing is approved automatically. Every decision is yours.

---

### STEP 8 — Export the Policy (Page: "Export Policy")

Once you have approved at least one rule, click "Export."
Choose format: JSON or XACML.

You get a policy document like this:

```json
{
  "policy_id": "pol_001",
  "default_decision": "deny",
  "rules": [
    {
      "rule_id": "R001",
      "effect": "permit",
      "action": "read",
      "conditions": [
        {"attribute": "user.department", "operator": "==", "value": "radiology"},
        {"attribute": "resource.sensitivity", "operator": "==", "value": "high"}
      ]
    }
  ]
}
```

This file can be loaded into any ABAC policy enforcement system.

---

### What happens if something goes wrong?

| Situation | What the system does |
|---|---|
| Wrong file format | Returns error: "Use CSV or JSON only" |
| Missing column | Returns error: "user_id column missing in users.csv" |
| Export before approval | Returns error: "Approve at least one rule first" |
| Server error | Returns "deny" — never accidentally permits access |
| File too large | Returns error: "File exceeds 10 MB limit" |

---

---

# PART 4 — PROJECT PRESENTATION FLOW (How to Present)

---

## Recommended Order for 15-20 Minute Presentation

---

### SLIDE 1 — Title Slide (30 seconds)

Say:
"Good morning/afternoon. Our project is titled Supervised Learning Based
Approach for Mining ABAC Rules from Existing RBAC Enabled Systems.
In simple words — we use machine learning to automatically convert an
old role-based access control system into a smarter attribute-based one."

---

### SLIDE 2 — Problem Statement (1 minute)

Say:
"Every organisation manages who can access what. Most use RBAC — Role-Based
Access Control. As organisations grow, roles multiply and become hard to
manage. ABAC is a better solution but writing ABAC rules manually takes
months and is error-prone. Our system automates this conversion using
supervised machine learning."

Show: A simple diagram — RBAC on left, arrow with ML in middle, ABAC on right.

---

### SLIDE 3 — Objectives (1 minute)

Say:
"Our objectives are:
1. Import existing RBAC data and build the full authorisation matrix
2. Generate training samples and train three ML models
3. Extract human-readable ABAC rules from the Decision Tree
4. Let an administrator review and approve rules
5. Export the final policy as JSON or XACML"

---

### SLIDE 4 — System Architecture (2 minutes)

Say:
"The system has three layers.
First — the React frontend where the admin uploads data and reviews rules.
Second — the FastAPI backend which runs the entire pipeline.
Third — the Policy Engine which optimises and validates the rules.
All communication happens over REST APIs using JSON."

Show: The 3-tier architecture diagram.

---

### SLIDE 5 — Data Flow (2 minutes)

Say:
"The pipeline has 7 steps.
Step 1: Upload 6 CSV files.
Step 2: Build the authorisation matrix — all user-resource-permission combinations.
Step 3: Generate positive samples (authorised) and negative samples (not authorised).
Step 4: Train Decision Tree, Random Forest, and Gradient Boosting.
Step 5: Extract ABAC rules from the Decision Tree paths.
Step 6: Optimise — merge, generalise, and prune rules.
Step 7: Admin reviews and approves. Export the policy."

Show: The 7-step numbered flow diagram.

---

### SLIDE 6 — Tech Stack (1 minute)

Say:
"On the backend we use Python with FastAPI and scikit-learn.
For data processing — Pandas and NumPy.
For ML — Decision Tree, Random Forest, and Gradient Boosting from scikit-learn.
For the frontend — React.js with Tailwind CSS.
For testing — Pytest with 118 automated tests."

Show: Tech stack table.

---

### SLIDE 7 — Live Demo (3-4 minutes)

Say:
"Let me show you the system running live."

Run in terminal:
```
python scripts/run_demo.py --inline
```

Walk through each step as it prints:
- "We are uploading the hospital dataset — 12 users, 8 resources"
- "288 tuples computed, 200 authorised"
- "All 3 models trained in under 1 second, F1 = 1.0"
- "1 ABAC rule extracted — user reads permitted based on role patterns"
- "Policy validated on full 288 tuples — zero over-privilege, zero under-privilege"
- "Rule approved and exported as JSON"

---

### SLIDE 8 — Performance Evaluation Table (1 minute)

Say:
"All performance targets were met.
Precision, recall, and F1 all achieved 1.0 on our dataset.
Over-privilege and under-privilege rates are both zero.
The entire pipeline runs in under 1 second.
118 automated tests pass confirming correctness."

Show: The performance evaluation table.

---

### SLIDE 9 — Conclusion (1 minute)

Say:
"To summarise — we built a working prototype that:
Takes an existing RBAC system as input.
Uses a Decision Tree to mine human-readable ABAC rules automatically.
Lets an administrator review and approve rules before deployment.
Exports a complete policy with deny as the default decision for security.
All this runs in under 1 second and is fully reproducible with seed 42."

---

### SLIDE 10 — Future Work (30 seconds)

Say:
"Future enhancements include:
- Support for environmental attributes like time and location
- Integration with live IAM systems
- Deny-rule mining for negative permissions
- GPU-based training for very large datasets"

---

### SLIDE 11 — Q&A

Say:
"Thank you. We are happy to take questions."

---

## Tips for Answering Questions

| If asked about... | Key points to say |
|---|---|
| Why Decision Tree? | Interpretable — each path is a rule. RF and GB are black boxes. |
| Why not use RF rules? | RF has 100 trees — combining them gives no single readable rule. |
| What if F1 is not 1.0? | On real messy data it won't be. 1.0 is because our demo dataset has clean patterns. |
| Is this production ready? | It's an academic prototype. Production needs security audit and IAM integration. |
| What is deny by default? | If no rule matches, access is denied. Never accidentally grant access. |
| How is it different from manual? | Manual takes months. Our system takes under 1 second. |
| Can it handle 10000 users? | Yes — the algorithm scales. Training time increases but the method is the same. |

---

---

# PART 5 — SYSTEM ARCHITECTURE SUMMARY (for Architecture Diagram)

---

## Components and Connections

```
┌──────────────────────────────────────────────────┐
│           REACT FRONTEND  (Port 5173)            │
│   Upload → Matrix → Train → Rules → Review →    │
│              Validate → Export                   │
└───────────────────┬──────────────────────────────┘
                    │ HTTP REST JSON
                    │ /api/v1/*
┌───────────────────▼──────────────────────────────┐
│         FASTAPI BACKEND  (Port 8000)             │
│                                                  │
│  Data Pipeline          ML Engine                │
│  ─────────────          ──────────               │
│  loader.py              train.py                 │
│  auth_matrix.py         evaluate.py              │
│  preprocess.py          extract_rules.py         │
│  sampling.py                                     │
│                                                  │
│  Services (pipeline_service.py)                  │
│  State Store (state_store.py)                    │
└───────────────────┬──────────────────────────────┘
                    │ Python function calls
┌───────────────────▼──────────────────────────────┐
│           POLICY ENGINE                          │
│   optimise_policy()                              │
│   validate_policy()   ← full access matrix       │
│   export_policy()     ← JSON / XACML             │
└──────────────────────────────────────────────────┘

         ↕ All layers use ↕
┌──────────────────────────────────────────────────┐
│    SHARED CONTRACTS  (contracts.py)              │
│    Single source of truth for all data shapes    │
└──────────────────────────────────────────────────┘
```

---

## 9 API Endpoints

| # | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | POST | /api/v1/datasets/upload | Upload 6 RBAC files |
| 2 | GET | /api/v1/datasets/{id}/authorisation | View auth matrix |
| 3 | POST | /api/v1/training/run | Train all 3 models |
| 4 | GET | /api/v1/training/{run_id}/comparison | Compare model metrics |
| 5 | GET | /api/v1/training/{run_id}/rules | Get extracted ABAC rules |
| 6 | POST | /api/v1/policies/optimise/{run_id} | Optimise rule set |
| 7 | GET | /api/v1/policies/{id}/validation | Validate vs full matrix |
| 8 | POST | /api/v1/policies/{id}/review | Admin approve/reject/edit |
| 9 | POST | /api/v1/policies/{id}/export | Export JSON or XACML |

---

## Rule Lifecycle

```
candidate → optimised → approved → exported
                     ↘ rejected  (never exported)
           edited (needs re-approval before export)
```

---

*Document generated: November 2026*
*Project: RBAC-to-ABAC Miner | SITRC Nashik | Sandip Foundation*
