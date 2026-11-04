"""Test all generated datasets against the live backend."""
import httpx
from pathlib import Path

BASE   = "http://localhost:8000/api/v1"
ROOT   = Path(__file__).resolve().parent.parent
TABLES = ["users", "roles", "permissions", "user_roles", "role_permissions", "resources"]


def upload_dataset(name: str) -> dict:
    path = ROOT / "data_engineering" / "sample_datasets" / name
    files = {}
    for t in TABLES:
        csv_path = path / f"{t}.csv"
        files[t] = (f"{t}.csv", csv_path.read_bytes(), "text/csv")
    r = httpx.post(
        f"{BASE}/datasets/upload",
        files=files,
        data={"dataset_name": name, "file_format": "csv"},
        timeout=30,
    )
    return r.json()


def main():
    datasets = ["small", "hospital", "university", "fintech"]
    print(f"\n{'Dataset':<14} {'Status':<8} {'Users':>5} {'Roles':>5} "
          f"{'Perms':>5} {'Res':>5} {'Issues':>6}")
    print("-" * 55)

    all_ok = True
    for ds in datasets:
        body = upload_dataset(ds)
        if body.get("status") == "ok":
            s = body["summary"]
            issues = len(body.get("issues", []))
            print(f"{ds:<14} {'ok':<8} {s['n_users']:>5} {s['n_roles']:>5} "
                  f"{s['n_permissions']:>5} {s['n_resources']:>5} {issues:>6}")
        else:
            errors = [i["message"] for i in body.get("issues", []) if i["severity"] == "error"]
            print(f"{ds:<14} {'FAILED':<8}  -- {errors[:2]}")
            all_ok = False

    print()
    if all_ok:
        print("All datasets validated successfully.")
    else:
        print("Some datasets failed — check errors above.")


if __name__ == "__main__":
    main()
