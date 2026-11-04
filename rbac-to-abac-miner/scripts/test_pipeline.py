"""Test the full ML pipeline on all datasets — runs inline (no HTTP timeout)."""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.disable(logging.CRITICAL)   # suppress noise

from shared.schemas.contracts import DatasetUploadRequest, TrainingConfigRequest
from backend.services.pipeline_service import (
    upload_dataset, run_training, optimise_policy,
    get_extracted_rules, get_authorisation_response,
)
from backend.services import state_store

ROOT   = Path(__file__).resolve().parent.parent
TABLES = ["users", "roles", "permissions", "user_roles", "role_permissions", "resources"]


def load_dataset(name: str) -> str:
    path = ROOT / "data_engineering" / "sample_datasets" / name
    files = {t: (path / f"{t}.csv").read_bytes() for t in TABLES}
    req = DatasetUploadRequest(dataset_name=name, file_format="csv")
    result = upload_dataset(req, files)
    assert result.status == "ok", f"Upload failed for {name}: {result.issues}"
    return result.dataset_id


def pipeline(ds_id: str, name: str) -> dict:
    cfg = TrainingConfigRequest(
        dataset_id=ds_id,
        models=["decision_tree", "random_forest", "gradient_boosting"],
        random_seed=42, cv_folds=5, f1_target=0.8,
        min_support=0.02, min_confidence=0.7,
    )
    tr = run_training(cfg)
    rules_resp = get_extracted_rules(tr.run_id)
    opt = optimise_policy(tr.run_id)
    auth = get_authorisation_response(ds_id)

    models = {m.model_name: m.metrics.f1 for m in tr.models}
    return {
        "tuples":    auth.total_possible_tuples,
        "density":   auth.authorisation_density * 100,
        "dt_f1":     models.get("decision_tree", 0),
        "rf_f1":     models.get("random_forest", 0),
        "gb_f1":     models.get("gradient_boosting", 0),
        "n_rules":   rules_resp.n_rules,
        "opt_rules": opt.optimisation.rules_after,
        "pol_f1":    opt.metrics.f1,
        "pol_prec":  opt.metrics.precision,
        "pol_rec":   opt.metrics.recall,
        "opr":       opt.metrics.over_privilege_rate,
        "upr":       opt.metrics.under_privilege_rate,
        "wsc":       opt.metrics.wsc,
    }


def main():
    datasets = ["small", "hospital", "university", "fintech"]

    print(f"\n{'Dataset':<14} {'Tuples':>8} {'Auth%':>6} {'DT F1':>7} "
          f"{'RF F1':>7} {'GB F1':>7} {'Rules':>6} {'→Opt':>5} {'Pol F1':>8} "
          f"{'OPR':>6} {'UPR':>6}")
    print("─" * 92)

    for ds in datasets:
        print(f"  running {ds} ...", end="\r")
        ds_id = load_dataset(ds)
        r = pipeline(ds_id, ds)
        print(f"{ds:<14} {r['tuples']:>8,} {r['density']:>5.1f}% "
              f"{r['dt_f1']:>7.4f} {r['rf_f1']:>7.4f} {r['gb_f1']:>7.4f} "
              f"{r['n_rules']:>6} {r['opt_rules']:>5} {r['pol_f1']:>8.4f} "
              f"{r['opr']:>6.4f} {r['upr']:>6.4f}")

    print("\n✓ All datasets processed successfully.")


if __name__ == "__main__":
    main()
