"""Generate docs/modules/DATA_CONTRACTS.md from shared/schemas/contracts.py.

Run from anywhere: python scripts/generate_contract_docs.py
Re-run after every approved contract change (owner: Jayed). Requires pydantic>=2.
"""
import re, sys, json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "shared" / "schemas"))
import contracts as c
from pydantic_core import PydanticUndefined

from enum import Enum
def render(t):
    if isinstance(t, type) and issubclass(t, Enum):
        return "one of " + ", ".join(repr(m.value) for m in t)
    s = str(t)
    s = re.sub(r"<class '([^']+)'>", lambda m: m.group(1).split(".")[-1], s)
    s = s.replace("typing.", "").replace("contracts.", "")
    s = re.sub(r"Literal\[(.*?)\]", lambda m: "one of " + m.group(1), s)
    return s.replace("|", "\\|")

def table(model):
    rows = ["| Field | Type | Required | Default / constraint |", "|---|---|---|---|"]
    for name, f in model.model_fields.items():
        req = "yes" if f.is_required() else "no"
        dv = f.default.value if isinstance(f.default, Enum) else f.default
        d = "" if f.is_required() else (f"`{dv!r}`" if f.default is not PydanticUndefined and f.default_factory is None else "factory")
        cons = [f"{type(m).__name__}={getattr(m, k)}" for m in f.metadata for k in ("ge","le","gt","lt","min_length","max_length") if hasattr(m, k) and getattr(m, k) is not None]
        extra = ", ".join(([d] if d else []) + cons)
        if f.description: extra = (extra + "; " if extra else "") + f.description.replace("|", "\\|")
        rows.append(f"| `{name}` | `{render(f.annotation)}` | {req} | {extra} |")
    return "\n".join(rows)

CONTRACTS = [
 (1, "Dataset upload request", "POST /api/v1/datasets/upload", ["DatasetUploadRequest"], None, None),
 (2, "Dataset validation response", "same call", ["DatasetValidationResponse", "ValidationIssue", "DatasetSummary"], "dataset_validation_ok.json", "dataset_validation_invalid.json"),
 (3, "RBAC authorisation response", "GET /api/v1/datasets/{dataset_id}/authorisation", ["RBACAuthorisationResponse", "AuthorisationTuple"], "rbac_authorisation.json", None),
 (4, "Training configuration request", "POST /api/v1/training/run", ["TrainingConfigRequest", "NegativeSamplingConfig", "ModelHyperparams"], "training_request.json", None),
 (5, "Model training response", "same call", ["TrainingResponse", "TrainedModelInfo", "ModelMetrics"], "training_response.json", None),
 (6, "Model comparison response", "GET /api/v1/training/{run_id}/comparison", ["ModelComparisonResponse", "ModelComparisonRow"], "model_comparison.json", None),
 (7, "Extracted ABAC rule", "GET /api/v1/training/{run_id}/rules", ["ExtractedRulesResponse", "ABACRule", "Condition"], "extracted_rules.json", None),
 (8, "Optimised policy response", "POST /api/v1/policies/optimise/{run_id}", ["OptimisedPolicyResponse", "OptimisationSummary", "PolicyMetrics"], "optimised_policy.json", None),
 (9, "Policy validation response", "GET /api/v1/policies/{policy_id}/validation", ["PolicyValidationResponse"], "policy_validation.json", None),
 (10, "Administrator approval request", "POST /api/v1/policies/{policy_id}/review", ["ApprovalRequest", "RuleDecision", "ApprovalResponse"], "approval_request.json", "approval_response.json"),
 (11, "JSON export response", "POST /api/v1/policies/{policy_id}/export", ["ExportRequest", "ExportResponse"], "export_request.json", "export_response.json"),
]

out = [f"""# Data Contracts (contract version {c.CONTRACT_VERSION})

**Owner:** Jayed. **Source of truth:** `shared/schemas/contracts.py` (Pydantic v2). **Mocks:** `shared/sample_responses/`.
This file is **generated** from `contracts.py` by the script described in `shared/README.md`. Do not edit the field tables by hand; change `contracts.py` through a change request (`docs/development_rules/CHANGE_REQUEST_TEMPLATE.md`), then regenerate.

## Rules

1. Every request and response in the system is one of the models below. No ad-hoc dicts across module boundaries.
2. Required vs optional is exactly as in the tables. A field marked `no` may be omitted by the sender; receivers must tolerate its absence.
3. Frontend mocks, backend responses and `policy_engine` inputs/outputs follow the same models.
4. Any change (add, remove, rename, retype a field) needs approval of all four members, a `CONTRACT_VERSION` bump and regenerated samples.
5. Errors always use `ErrorResponse`:

```json
{json.dumps(json.loads((root/'shared/sample_responses/error_response.json').read_text()), indent=2)}
```

6. Enumerations: rule `status` is one of `candidate, optimised, approved, rejected, edited`; `effect` is always `permit` (deny-rule mining is out of scope); condition operators are `==, !=, in, not_in, <=, >, >=, <`.
7. Attribute names in conditions are prefixed: `user.<attribute>` or `resource.<attribute>`.
8. Timestamps are ISO-8601 UTC strings.

## Dataset file formats (inputs to contract 1)

CSV: six files, header row. JSON: one object, key per table, array of records, for example:

```json
{{
  "users": [{{"user_id": "u1", "department": "Finance", "position": "Analyst"}}],
  "roles": [{{"role_id": "r_fin", "role_name": "Finance Analyst"}}],
  "permissions": [{{"permission_id": "read"}}],
  "user_roles": [{{"user_id": "u1", "role_id": "r_fin"}}],
  "role_permissions": [{{"role_id": "r_fin", "permission_id": "read", "resource_id": ""}}],
  "resources": [{{"resource_id": "res1", "sensitivity": "low", "type": "report"}}]
}}
```

Column rules are in `docs/modules/DATA_PIPELINE.md`.
"""]

for n, title, ep, models, ex1, ex2 in CONTRACTS:
    out.append(f"## Contract {n}: {title}\n\n**Endpoint:** `{ep}`\n")
    for m in models:
        out.append(f"### `{m}`\n\n{table(getattr(c, m))}\n")
    if ex1 is None:
        out.append("**Example request (metadata part of the multipart form):**\n\n```json\n" + json.dumps({"dataset_name": "hospital_small", "file_format": "csv"}, indent=2) + "\n```\n\nThe response is contract 2.\n")
    else:
        for label, fn in (("example", ex1), ("example", ex2)):
            if fn:
                kind = "request" if "request" in fn else "response"
                out.append(f"**Example {kind}** (`shared/sample_responses/{fn}`):\n\n```json\n" + json.dumps(json.loads((root/'shared/sample_responses'/fn).read_text()), indent=2) + "\n```\n")
    out.append("**Error:** `ErrorResponse` (see Rules).\n")

(root / "docs/modules/DATA_CONTRACTS.md").write_text("\n".join(out), encoding="utf-8")
print("written", len("\n".join(out).splitlines()), "lines")
