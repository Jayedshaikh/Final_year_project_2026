#!/usr/bin/env python
"""Demo script: full RBAC-to-ABAC pipeline in one command.

Runs the complete flow on the seed_hospital dataset with seed 42:
  1. Upload dataset
  2. Inspect authorisation matrix
  3. Train models
  4. Compare models
  5. Extract rules
  6. Optimise policy (stub until Granthali's module is ready)
  7. Validate policy
  8. Approve first rule
  9. Export approved policy as JSON

Usage (from repository root):
    python scripts/run_demo.py

The backend must be running:
    uvicorn backend.app.main:app --reload --port 8000

Or run inline without a server (uses TestClient):
    python scripts/run_demo.py --inline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow import from repository root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATASET_DIR = ROOT / "data_engineering" / "sample_datasets" / "seed_hospital"
BASE_URL = "http://localhost:8000"


def _client(inline: bool):
    """Return an HTTP client — TestClient (inline) or httpx.Client (live)."""
    if inline:
        from backend.app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    import httpx
    return httpx.Client(base_url=BASE_URL, timeout=60)


def run_demo(inline: bool = False) -> None:
    """Execute the full end-to-end demo flow."""
    client = _client(inline)
    sep = "=" * 60

    print(sep)
    print("RBAC-to-ABAC Miner — Demo (seed=42, dataset=seed_hospital)")
    print(sep)

    # ------------------------------------------------------------------ #
    # 1. Upload dataset
    # ------------------------------------------------------------------ #
    print("\n[1] Uploading seed_hospital dataset …")
    table_files = ["users", "roles", "permissions", "user_roles", "role_permissions", "resources"]
    files = {}
    for t in table_files:
        path = DATASET_DIR / f"{t}.csv"
        if not path.exists():
            print(f"  ERROR: {path} not found. Run from the repository root.")
            sys.exit(1)
        files[t] = (f"{t}.csv", path.read_bytes(), "text/csv")

    resp = client.post(
        "/api/v1/datasets/upload",
        files=files,
        data={"dataset_name": "seed_hospital", "file_format": "csv"},
    )
    _check(resp, "upload")
    body = resp.json()
    dataset_id = body["dataset_id"]
    summary = body["summary"]
    print(f"  dataset_id : {dataset_id}")
    print(f"  users={summary['n_users']}  roles={summary['n_roles']}  "
          f"permissions={summary['n_permissions']}  resources={summary['n_resources']}")
    if body.get("issues"):
        print(f"  warnings   : {len(body['issues'])} issue(s)")

    # ------------------------------------------------------------------ #
    # 2. Authorisation matrix
    # ------------------------------------------------------------------ #
    print(f"\n[2] RBAC authorisation matrix for {dataset_id} …")
    resp = client.get(f"/api/v1/datasets/{dataset_id}/authorisation")
    _check(resp, "authorisation")
    auth = resp.json()
    print(f"  total tuples  : {auth['total_possible_tuples']}")
    print(f"  authorised    : {auth['n_authorised']}")
    print(f"  density       : {auth['authorisation_density']:.3f}")

    # ------------------------------------------------------------------ #
    # 3. Train models
    # ------------------------------------------------------------------ #
    print("\n[3] Training DT / RF / GB (seed=42, cv_folds=5) …")
    train_cfg = {
        "dataset_id": dataset_id,
        "models": ["decision_tree", "random_forest", "gradient_boosting"],
        "random_seed": 42,
        "cv_folds": 5,
        "f1_target": 0.85,
        "min_support": 0.01,
        "min_confidence": 0.8,
        "negative_sampling": {"strategy": "random", "ratio": 1.0},
    }
    resp = client.post("/api/v1/training/run", json=train_cfg)
    _check(resp, "training/run")
    train = resp.json()
    run_id = train["run_id"]
    print(f"  run_id        : {run_id}")
    print(f"  train/test    : {train['n_train']} / {train['n_test']}")
    print(f"  f1_target_met : {train['f1_target_met']}")
    for m in train["models"]:
        print(f"  {m['model_name']:<20} f1={m['metrics']['f1']:.4f}  "
              f"p={m['metrics']['precision']:.4f}  r={m['metrics']['recall']:.4f}  "
              f"time={m['metrics']['training_time_seconds']:.3f}s")

    # ------------------------------------------------------------------ #
    # 4. Model comparison
    # ------------------------------------------------------------------ #
    print(f"\n[4] Model comparison for {run_id} …")
    resp = client.get(f"/api/v1/training/{run_id}/comparison")
    _check(resp, "comparison")
    cmp = resp.json()
    print(f"  selected for extraction: {cmp['selected_for_extraction']}")
    print(f"  reason: {cmp['selection_reason']}")

    # ------------------------------------------------------------------ #
    # 5. Extracted rules
    # ------------------------------------------------------------------ #
    print(f"\n[5] Extracted ABAC rules for {run_id} …")
    resp = client.get(f"/api/v1/training/{run_id}/rules")
    _check(resp, "rules")
    rules_resp = resp.json()
    print(f"  n_rules : {rules_resp['n_rules']}")
    for i, r in enumerate(rules_resp["rules"][:3]):
        print(f"  {r['rule_id']}  action={r['action']}  "
              f"support={r['support']:.3f}  confidence={r['confidence']:.3f}  "
              f"conditions={len(r['conditions'])}")
    if rules_resp["n_rules"] > 3:
        print(f"  … ({rules_resp['n_rules'] - 3} more)")

    if rules_resp["n_rules"] == 0:
        print("  No rules extracted (adjust min_support/min_confidence). Stopping demo.")
        return

    # ------------------------------------------------------------------ #
    # 6. Optimise policy
    # ------------------------------------------------------------------ #
    print(f"\n[6] Optimising policy from {run_id} …")
    resp = client.post(f"/api/v1/policies/optimise/{run_id}")
    _check(resp, "optimise")
    opt = resp.json()
    policy_id = opt["policy_id"]
    print(f"  policy_id     : {policy_id}")
    print(f"  rules before  : {opt['optimisation']['rules_before']}")
    print(f"  rules after   : {opt['optimisation']['rules_after']}")
    print(f"  policy f1     : {opt['metrics']['f1']:.4f}")

    # ------------------------------------------------------------------ #
    # 7. Policy validation
    # ------------------------------------------------------------------ #
    print(f"\n[7] Validating policy {policy_id} …")
    resp = client.get(f"/api/v1/policies/{policy_id}/validation")
    _check(resp, "validation")
    val = resp.json()
    m = val["metrics"]
    print(f"  precision={m['precision']:.4f}  recall={m['recall']:.4f}  f1={m['f1']:.4f}")
    print(f"  OPR={m['over_privilege_rate']:.4f}  UPR={m['under_privilege_rate']:.4f}  "
          f"WSC={m['wsc']:.1f}  rules={m['rule_count']}")
    print(f"  evaluated on  : {m['evaluated_on']}  ({m['n_tuples_evaluated']} tuples)")

    # ------------------------------------------------------------------ #
    # 8. Approve first rule
    # ------------------------------------------------------------------ #
    first_rule_id = opt["rules"][0]["rule_id"] if opt["rules"] else None
    if not first_rule_id:
        print("\n  No optimised rules to approve. Stopping.")
        return

    print(f"\n[8] Approving rule {first_rule_id} …")
    review_payload = {
        "policy_id": policy_id,
        "reviewer": "demo_admin",
        "decisions": [{"rule_id": first_rule_id, "decision": "approve", "comment": "Demo approval"}],
    }
    resp = client.post(f"/api/v1/policies/{policy_id}/review", json=review_payload)
    _check(resp, "review")
    review = resp.json()
    print(f"  approved={review['n_approved']}  rejected={review['n_rejected']}  "
          f"unreviewed={review['n_still_unreviewed']}")

    # ------------------------------------------------------------------ #
    # 9. Export JSON policy
    # ------------------------------------------------------------------ #
    print(f"\n[9] Exporting approved policy {policy_id} as JSON …")
    resp = client.post(
        f"/api/v1/policies/{policy_id}/export",
        json={"policy_id": policy_id, "format": "json"},
    )
    _check(resp, "export")
    export = resp.json()
    print(f"  n_rules_exported  : {export['n_rules_exported']}")
    print(f"  default_decision  : {export['default_decision']}")
    print(f"  generated_at      : {export['generated_at']}")

    # Pretty-print the first 20 lines of the policy document
    content_lines = export["content"].splitlines()
    print("\n  Policy document (first 20 lines):")
    for line in content_lines[:20]:
        print(f"    {line}")
    if len(content_lines) > 20:
        print(f"    … ({len(content_lines) - 20} more lines)")

    print(f"\n{sep}")
    print("Demo complete. All 9 steps succeeded.")
    print(f"  dataset_id={dataset_id}  run_id={run_id}  policy_id={policy_id}")
    print(sep)


def _check(resp, label: str) -> None:
    """Assert an HTTP response is 200; print the body and exit if not."""
    if resp.status_code != 200:
        print(f"\n  FAILED [{label}]: HTTP {resp.status_code}")
        try:
            print(f"  {json.dumps(resp.json(), indent=2)}")
        except Exception:
            print(f"  {resp.text}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RBAC-to-ABAC Miner demo")
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Run via FastAPI TestClient (no server needed)",
    )
    args = parser.parse_args()

    # Suppress INFO/WARNING logs to stderr so the demo output is clean
    import logging
    logging.getLogger().setLevel(logging.ERROR)

    run_demo(inline=args.inline)
