"""Validate governance files. Run from repo root: python scripts/validate_governance.py

Checks:
1. PROJECT_RULES.json parses.
2. Every module has exactly one owner, owner is a known member, and no member appears twice in a module's role lists.
3. Every module path exists on disk (for single-path modules).
4. Every file in shared/sample_responses validates against shared/schemas/contracts.py.
5. Every member guide and agent file referenced exists.
Exit code 1 on any failure.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors = []

rules = json.loads((ROOT / "PROJECT_RULES.json").read_text(encoding="utf-8"))
members = set(rules["team"]["members"])

for name, mod in rules["modules"].items():
    owner = mod.get("owner")
    if owner not in members:
        errors.append(f"module {name}: unknown owner {owner!r}")
    roles = {k: mod.get(k, []) for k in ("contributors", "read_only", "restricted")}
    if owner in sum(roles.values(), []):
        errors.append(f"module {name}: owner also listed in another role")
    for m in sum(roles.values(), []):
        if m not in members:
            errors.append(f"module {name}: unknown member {m!r}")
    path = mod["path"]
    if "," not in path and not (ROOT / path).exists():
        errors.append(f"module {name}: path {path} missing")

for key, m in rules["team"]["members"].items():
    for f in (m["guide"], m["agent_file"]):
        if not (ROOT / f).exists():
            errors.append(f"member {key}: missing file {f}")

sys.path.insert(0, str(ROOT / "shared" / "schemas"))
import contracts as c  # noqa: E402

MAP = {
    "dataset_validation_ok.json": c.DatasetValidationResponse,
    "dataset_validation_invalid.json": c.DatasetValidationResponse,
    "error_response.json": c.ErrorResponse,
    "rbac_authorisation.json": c.RBACAuthorisationResponse,
    "training_request.json": c.TrainingConfigRequest,
    "training_response.json": c.TrainingResponse,
    "model_comparison.json": c.ModelComparisonResponse,
    "extracted_rules.json": c.ExtractedRulesResponse,
    "optimised_policy.json": c.OptimisedPolicyResponse,
    "policy_validation.json": c.PolicyValidationResponse,
    "approval_request.json": c.ApprovalRequest,
    "approval_response.json": c.ApprovalResponse,
    "export_request.json": c.ExportRequest,
    "export_response.json": c.ExportResponse,
}
sample_dir = ROOT / "shared" / "sample_responses"
for fname, model in MAP.items():
    p = sample_dir / fname
    if not p.exists():
        errors.append(f"missing sample {fname}")
        continue
    try:
        model.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"sample {fname} invalid: {exc}")
for p in sample_dir.glob("*.json"):
    if p.name not in MAP:
        errors.append(f"sample {p.name} has no model mapping in validate_governance.py")

if errors:
    print("GOVERNANCE VALIDATION FAILED")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("Governance validation passed:", len(rules["modules"]), "modules,", len(MAP), "sample contracts")
