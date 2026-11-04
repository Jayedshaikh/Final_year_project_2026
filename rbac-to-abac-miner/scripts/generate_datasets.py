"""Generate large, realistic RBAC sample datasets.

Creates three domain datasets:
  1. hospital   — 200 users, 20 roles, 5 permissions, 150 resources
  2. university — 300 users, 15 roles, 4 permissions, 200 resources
  3. fintech    — 250 users, 18 roles, 6 permissions, 180 resources

Each domain has a different attribute profile so the Decision Tree learns
meaningfully different ABAC rules per dataset.

Usage:
    python scripts/generate_datasets.py
    python scripts/generate_datasets.py --seed 99   # custom seed

Output:
    data_engineering/sample_datasets/hospital/
    data_engineering/sample_datasets/university/
    data_engineering/sample_datasets/fintech/
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "data_engineering" / "sample_datasets"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  wrote {path.name:30s}  ({len(df):>5} rows)")


# ─────────────────────────────────────────────────────────────────────────────
# 1. HOSPITAL DATASET  (200 users · 20 roles · 5 permissions · 150 resources)
# ─────────────────────────────────────────────────────────────────────────────

def generate_hospital(seed: int) -> None:
    print("\n[Hospital]  100 users · 20 roles · 5 perms · 80 resources")
    rng = _rng(seed)
    base = OUT / "hospital"

    departments  = ["cardiology", "radiology", "oncology", "neurology", "emergency",
                    "icu", "surgery", "pharmacy", "lab", "administration"]
    positions    = ["doctor", "nurse", "technician", "admin", "receptionist",
                    "pharmacist", "lab_analyst", "director", "intern", "consultant"]
    clearances   = ["public", "internal", "confidential", "secret"]
    shift_types  = ["day", "night", "rotating"]

    # ── users ──────────────────────────────────────────────────────────────
    n_users = 100
    user_ids = [f"U{i:04d}" for i in range(1, n_users + 1)]
    users = pd.DataFrame({
        "user_id":        user_ids,
        "department":     rng.choice(departments, n_users),
        "position":       rng.choice(positions,   n_users),
        "seniority_years": rng.integers(1, 30,    n_users),
        "clearance":      rng.choice(clearances,  n_users),
        "shift":          rng.choice(shift_types, n_users),
    })
    _save(users, base / "users.csv")

    # ── roles ───────────────────────────────────────────────────────────────
    role_defs = [
        ("R_SENIOR_DOCTOR",    "Senior Doctor"),
        ("R_JUNIOR_DOCTOR",    "Junior Doctor"),
        ("R_HEAD_NURSE",       "Head Nurse"),
        ("R_STAFF_NURSE",      "Staff Nurse"),
        ("R_RADIOLOGIST",      "Radiologist"),
        ("R_CARDIOLOGIST",     "Cardiologist"),
        ("R_ONCOLOGIST",       "Oncologist"),
        ("R_NEUROLOGIST",      "Neurologist"),
        ("R_SURGEON",          "Surgeon"),
        ("R_PHARMACIST",       "Pharmacist"),
        ("R_LAB_ANALYST",      "Lab Analyst"),
        ("R_ICU_SPECIALIST",   "ICU Specialist"),
        ("R_RECEPTIONIST",     "Receptionist"),
        ("R_ADMIN_STAFF",      "Admin Staff"),
        ("R_DEPT_DIRECTOR",    "Department Director"),
        ("R_INTERN",           "Medical Intern"),
        ("R_CONSULTANT",       "External Consultant"),
        ("R_TECH_SUPPORT",     "Tech Support"),
        ("R_EMERGENCY_RESP",   "Emergency Responder"),
        ("R_PHARMACY_TECH",    "Pharmacy Technician"),
    ]
    roles = pd.DataFrame(role_defs, columns=["role_id", "role_name"])
    _save(roles, base / "roles.csv")

    # ── permissions ─────────────────────────────────────────────────────────
    perms = pd.DataFrame({"permission_id": ["read", "write", "delete", "approve", "audit"]})
    _save(perms, base / "permissions.csv")

    # ── resources ───────────────────────────────────────────────────────────
    n_res = 80
    res_types        = ["patient_record", "lab_result", "prescription", "imaging",
                        "billing_record", "staff_schedule", "inventory", "audit_log",
                        "research_data", "insurance_claim"]
    sensitivities    = ["public", "internal", "restricted", "highly_restricted"]
    res_departments  = departments

    resource_ids = [f"RES{i:04d}" for i in range(1, n_res + 1)]
    resources = pd.DataFrame({
        "resource_id":   resource_ids,
        "type":          rng.choice(res_types,       n_res),
        "sensitivity":   rng.choice(sensitivities,   n_res),
        "department":    rng.choice(res_departments, n_res),
        "is_critical":   rng.choice(["yes", "no"],   n_res),
    })
    _save(resources, base / "resources.csv")

    # ── user_roles (UA) ─────────────────────────────────────────────────────
    role_ids = [r[0] for r in role_defs]
    # Each user gets 1–3 roles based on their position
    pos_to_roles = {
        "doctor":      ["R_SENIOR_DOCTOR", "R_JUNIOR_DOCTOR", "R_CARDIOLOGIST",
                        "R_ONCOLOGIST", "R_NEUROLOGIST", "R_SURGEON"],
        "nurse":       ["R_HEAD_NURSE", "R_STAFF_NURSE", "R_ICU_SPECIALIST"],
        "technician":  ["R_LAB_ANALYST", "R_RADIOLOGIST", "R_PHARMACY_TECH", "R_TECH_SUPPORT"],
        "admin":       ["R_ADMIN_STAFF", "R_DEPT_DIRECTOR"],
        "receptionist":["R_RECEPTIONIST"],
        "pharmacist":  ["R_PHARMACIST", "R_PHARMACY_TECH"],
        "lab_analyst": ["R_LAB_ANALYST"],
        "director":    ["R_DEPT_DIRECTOR"],
        "intern":      ["R_INTERN"],
        "consultant":  ["R_CONSULTANT", "R_EMERGENCY_RESP"],
    }
    ua_rows = []
    for _, u in users.iterrows():
        candidates = pos_to_roles.get(u["position"], ["R_ADMIN_STAFF"])
        n_assign = rng.integers(1, min(3, len(candidates)) + 1)
        chosen = rng.choice(candidates, size=int(n_assign), replace=False)
        for r in chosen:
            ua_rows.append({"user_id": u["user_id"], "role_id": r})
    user_roles = pd.DataFrame(ua_rows).drop_duplicates()
    _save(user_roles, base / "user_roles.csv")

    # ── role_permissions (PA) ───────────────────────────────────────────────
    role_perm_map = {
        "R_SENIOR_DOCTOR":  [("read",""), ("write",""), ("approve","")],
        "R_JUNIOR_DOCTOR":  [("read",""), ("write","")],
        "R_HEAD_NURSE":     [("read",""), ("write",""), ("approve","")],
        "R_STAFF_NURSE":    [("read",""), ("write","")],
        "R_RADIOLOGIST":    [("read",""), ("write","")],
        "R_CARDIOLOGIST":   [("read",""), ("write",""), ("approve","")],
        "R_ONCOLOGIST":     [("read",""), ("write",""), ("approve","")],
        "R_NEUROLOGIST":    [("read",""), ("write","")],
        "R_SURGEON":        [("read",""), ("write",""), ("approve","")],
        "R_PHARMACIST":     [("read",""), ("write",""), ("approve","")],
        "R_LAB_ANALYST":    [("read",""), ("write","")],
        "R_ICU_SPECIALIST": [("read",""), ("write",""), ("approve","")],
        "R_RECEPTIONIST":   [("read","")],
        "R_ADMIN_STAFF":    [("read",""), ("write","")],
        "R_DEPT_DIRECTOR":  [("read",""), ("write",""), ("delete",""), ("approve",""), ("audit","")],
        "R_INTERN":         [("read","")],
        "R_CONSULTANT":     [("read",""), ("write","")],
        "R_TECH_SUPPORT":   [("read",""), ("write","")],
        "R_EMERGENCY_RESP": [("read",""), ("write",""), ("approve","")],
        "R_PHARMACY_TECH":  [("read",""), ("write","")],
    }
    pa_rows = []
    for role, perms_list in role_perm_map.items():
        for perm, res_scope in perms_list:
            pa_rows.append({"role_id": role, "permission_id": perm, "resource_id": res_scope})
    role_permissions = pd.DataFrame(pa_rows)
    _save(role_permissions, base / "role_permissions.csv")

    print(f"  Hospital dataset saved to: {base}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. UNIVERSITY DATASET  (300 users · 15 roles · 4 permissions · 200 resources)
# ─────────────────────────────────────────────────────────────────────────────

def generate_university(seed: int) -> None:
    print("\n[University]  120 users · 15 roles · 4 perms · 80 resources")
    rng = _rng(seed + 1)
    base = OUT / "university"

    faculties   = ["engineering", "medicine", "arts", "science", "law",
                   "business", "education", "architecture", "pharmacy", "it"]
    emp_types   = ["professor", "lecturer", "researcher", "admin_staff",
                   "student", "phd_candidate", "lab_technician", "librarian",
                   "hod", "dean"]
    tenure_cats = ["tenured", "probationary", "visiting", "contract"]
    campuses    = ["main", "north", "south", "online"]

    # ── users ──────────────────────────────────────────────────────────────
    n_users = 120
    user_ids = [f"USR{i:04d}" for i in range(1, n_users + 1)]
    users = pd.DataFrame({
        "user_id":        user_ids,
        "faculty":        rng.choice(faculties,   n_users),
        "employee_type":  rng.choice(emp_types,   n_users),
        "years_employed": rng.integers(0, 40,     n_users),
        "tenure_status":  rng.choice(tenure_cats, n_users),
        "campus":         rng.choice(campuses,    n_users),
    })
    _save(users, base / "users.csv")

    # ── roles ───────────────────────────────────────────────────────────────
    role_defs = [
        ("R_PROFESSOR",       "Full Professor"),
        ("R_ASSOCIATE_PROF",  "Associate Professor"),
        ("R_LECTURER",        "Lecturer"),
        ("R_RESEARCHER",      "Researcher"),
        ("R_PHD_CANDIDATE",   "PhD Candidate"),
        ("R_STUDENT",         "Student"),
        ("R_ADMIN",           "Administrative Staff"),
        ("R_HOD",             "Head of Department"),
        ("R_DEAN",            "Dean"),
        ("R_LAB_TECH",        "Lab Technician"),
        ("R_LIBRARIAN",       "Librarian"),
        ("R_IT_STAFF",        "IT Staff"),
        ("R_EXAMINER",        "External Examiner"),
        ("R_FINANCE_OFFICER", "Finance Officer"),
        ("R_REGISTRAR",       "Registrar"),
    ]
    roles = pd.DataFrame(role_defs, columns=["role_id", "role_name"])
    _save(roles, base / "roles.csv")

    # ── permissions ─────────────────────────────────────────────────────────
    perms = pd.DataFrame({"permission_id": ["read", "write", "delete", "submit"]})
    _save(perms, base / "permissions.csv")

    # ── resources ───────────────────────────────────────────────────────────
    n_res = 80
    res_types     = ["course_material", "exam_paper", "research_paper", "student_record",
                     "grade_sheet", "lab_data", "financial_record", "library_resource",
                     "staff_record", "thesis", "timetable", "policy_document"]
    access_levels = ["open", "restricted", "confidential", "top_secret"]
    res_faculties = faculties

    resource_ids = [f"RES{i:04d}" for i in range(1, n_res + 1)]
    resources = pd.DataFrame({
        "resource_id":   resource_ids,
        "type":          rng.choice(res_types,     n_res),
        "access_level":  rng.choice(access_levels, n_res),
        "faculty":       rng.choice(res_faculties, n_res),
        "is_digital":    rng.choice(["yes", "no"], n_res),
    })
    _save(resources, base / "resources.csv")

    # ── user_roles (UA) ─────────────────────────────────────────────────────
    emp_to_roles = {
        "professor":      ["R_PROFESSOR", "R_RESEARCHER", "R_EXAMINER"],
        "lecturer":       ["R_LECTURER", "R_ASSOCIATE_PROF"],
        "researcher":     ["R_RESEARCHER"],
        "admin_staff":    ["R_ADMIN", "R_FINANCE_OFFICER"],
        "student":        ["R_STUDENT"],
        "phd_candidate":  ["R_PHD_CANDIDATE", "R_RESEARCHER"],
        "lab_technician": ["R_LAB_TECH"],
        "librarian":      ["R_LIBRARIAN"],
        "hod":            ["R_HOD", "R_PROFESSOR"],
        "dean":           ["R_DEAN", "R_HOD"],
    }
    ua_rows = []
    for _, u in users.iterrows():
        candidates = emp_to_roles.get(u["employee_type"], ["R_ADMIN"])
        n_assign = rng.integers(1, min(3, len(candidates)) + 1)
        chosen = rng.choice(candidates, size=int(n_assign), replace=False)
        for r in chosen:
            ua_rows.append({"user_id": u["user_id"], "role_id": r})
    user_roles = pd.DataFrame(ua_rows).drop_duplicates()
    _save(user_roles, base / "user_roles.csv")

    # ── role_permissions (PA) ───────────────────────────────────────────────
    role_perm_map = {
        "R_PROFESSOR":       [("read",""), ("write",""), ("submit","")],
        "R_ASSOCIATE_PROF":  [("read",""), ("write",""), ("submit","")],
        "R_LECTURER":        [("read",""), ("write","")],
        "R_RESEARCHER":      [("read",""), ("write",""), ("submit","")],
        "R_PHD_CANDIDATE":   [("read",""), ("write","")],
        "R_STUDENT":         [("read","")],
        "R_ADMIN":           [("read",""), ("write",""), ("delete","")],
        "R_HOD":             [("read",""), ("write",""), ("delete",""), ("submit","")],
        "R_DEAN":            [("read",""), ("write",""), ("delete",""), ("submit","")],
        "R_LAB_TECH":        [("read",""), ("write","")],
        "R_LIBRARIAN":       [("read",""), ("write",""), ("delete","")],
        "R_IT_STAFF":        [("read",""), ("write",""), ("delete","")],
        "R_EXAMINER":        [("read",""), ("submit","")],
        "R_FINANCE_OFFICER": [("read",""), ("write",""), ("delete","")],
        "R_REGISTRAR":       [("read",""), ("write",""), ("delete",""), ("submit","")],
    }
    pa_rows = []
    for role, perms_list in role_perm_map.items():
        for perm, res_scope in perms_list:
            pa_rows.append({"role_id": role, "permission_id": perm, "resource_id": res_scope})
    role_permissions = pd.DataFrame(pa_rows)
    _save(role_permissions, base / "role_permissions.csv")

    print(f"  University dataset saved to: {base}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. FINTECH DATASET  (250 users · 18 roles · 6 permissions · 180 resources)
# ─────────────────────────────────────────────────────────────────────────────

def generate_fintech(seed: int) -> None:
    print("\n[Fintech]  100 users · 18 roles · 6 perms · 80 resources")
    rng = _rng(seed + 2)
    base = OUT / "fintech"

    departments  = ["trading", "risk", "compliance", "operations", "it",
                    "audit", "hr", "legal", "customer_support", "analytics"]
    job_levels   = ["analyst", "associate", "manager", "director", "vp",
                    "md", "intern", "contractor", "consultant", "cxo"]
    clearances   = ["level1", "level2", "level3", "level4", "level5"]
    regions      = ["apac", "emea", "americas", "global"]

    # ── users ──────────────────────────────────────────────────────────────
    n_users = 100
    user_ids = [f"EMP{i:05d}" for i in range(1, n_users + 1)]
    users = pd.DataFrame({
        "user_id":           user_ids,
        "department":        rng.choice(departments, n_users),
        "job_level":         rng.choice(job_levels,  n_users),
        "years_at_firm":     rng.integers(0, 25,     n_users),
        "security_clearance":rng.choice(clearances,  n_users),
        "region":            rng.choice(regions,     n_users),
        "is_certified":      rng.choice(["yes", "no"], n_users),
    })
    _save(users, base / "users.csv")

    # ── roles ───────────────────────────────────────────────────────────────
    role_defs = [
        ("R_TRADER",          "Trader"),
        ("R_RISK_ANALYST",    "Risk Analyst"),
        ("R_COMPLIANCE_OFF",  "Compliance Officer"),
        ("R_OPS_ANALYST",     "Operations Analyst"),
        ("R_IT_ENGINEER",     "IT Engineer"),
        ("R_AUDITOR",         "Internal Auditor"),
        ("R_HR_BUSINESS",     "HR Business Partner"),
        ("R_LEGAL_COUNSEL",   "Legal Counsel"),
        ("R_SUPPORT_AGENT",   "Customer Support Agent"),
        ("R_DATA_ANALYST",    "Data Analyst"),
        ("R_PORTFOLIO_MGR",   "Portfolio Manager"),
        ("R_RISK_MANAGER",    "Risk Manager"),
        ("R_IT_MANAGER",      "IT Manager"),
        ("R_COMPLIANCE_MGR",  "Compliance Manager"),
        ("R_DIRECTOR",        "Director"),
        ("R_VP",              "Vice President"),
        ("R_MD",              "Managing Director"),
        ("R_INTERN",          "Intern"),
    ]
    roles = pd.DataFrame(role_defs, columns=["role_id", "role_name"])
    _save(roles, base / "roles.csv")

    # ── permissions ─────────────────────────────────────────────────────────
    perms = pd.DataFrame({"permission_id": ["read", "write", "execute", "approve", "audit", "export"]})
    _save(perms, base / "permissions.csv")

    # ── resources ───────────────────────────────────────────────────────────
    n_res = 80
    res_types     = ["trade_order", "portfolio", "risk_report", "compliance_doc",
                     "client_data", "market_data", "audit_trail", "financial_model",
                     "regulatory_filing", "hr_record", "system_config", "analytics_dashboard"]
    risk_levels   = ["low", "medium", "high", "critical"]
    res_departments = departments

    resource_ids = [f"SYS{i:04d}" for i in range(1, n_res + 1)]
    resources = pd.DataFrame({
        "resource_id":   resource_ids,
        "type":          rng.choice(res_types,        n_res),
        "risk_level":    rng.choice(risk_levels,      n_res),
        "department":    rng.choice(res_departments,  n_res),
        "is_regulated":  rng.choice(["yes", "no"],    n_res),
    })
    _save(resources, base / "resources.csv")

    # ── user_roles (UA) ─────────────────────────────────────────────────────
    level_to_roles = {
        "analyst":    ["R_RISK_ANALYST", "R_DATA_ANALYST", "R_OPS_ANALYST", "R_TRADER"],
        "associate":  ["R_TRADER", "R_RISK_ANALYST", "R_SUPPORT_AGENT"],
        "manager":    ["R_RISK_MANAGER", "R_IT_MANAGER", "R_COMPLIANCE_MGR", "R_HR_BUSINESS"],
        "director":   ["R_DIRECTOR"],
        "vp":         ["R_VP"],
        "md":         ["R_MD"],
        "intern":     ["R_INTERN"],
        "contractor": ["R_IT_ENGINEER", "R_OPS_ANALYST"],
        "consultant": ["R_LEGAL_COUNSEL", "R_COMPLIANCE_OFF"],
        "cxo":        ["R_MD", "R_DIRECTOR"],
    }
    ua_rows = []
    for _, u in users.iterrows():
        candidates = level_to_roles.get(u["job_level"], ["R_INTERN"])
        n_assign = rng.integers(1, min(3, len(candidates)) + 1)
        chosen = rng.choice(candidates, size=int(n_assign), replace=False)
        for r in chosen:
            ua_rows.append({"user_id": u["user_id"], "role_id": r})
    user_roles = pd.DataFrame(ua_rows).drop_duplicates()
    _save(user_roles, base / "user_roles.csv")

    # ── role_permissions (PA) ───────────────────────────────────────────────
    role_perm_map = {
        "R_TRADER":         [("read",""), ("write",""), ("execute","")],
        "R_RISK_ANALYST":   [("read",""), ("write","")],
        "R_COMPLIANCE_OFF": [("read",""), ("write",""), ("audit","")],
        "R_OPS_ANALYST":    [("read",""), ("write","")],
        "R_IT_ENGINEER":    [("read",""), ("write",""), ("execute","")],
        "R_AUDITOR":        [("read",""), ("audit","")],
        "R_HR_BUSINESS":    [("read",""), ("write","")],
        "R_LEGAL_COUNSEL":  [("read",""), ("write",""), ("audit","")],
        "R_SUPPORT_AGENT":  [("read","")],
        "R_DATA_ANALYST":   [("read",""), ("export","")],
        "R_PORTFOLIO_MGR":  [("read",""), ("write",""), ("execute",""), ("approve","")],
        "R_RISK_MANAGER":   [("read",""), ("write",""), ("approve",""), ("audit","")],
        "R_IT_MANAGER":     [("read",""), ("write",""), ("execute",""), ("audit","")],
        "R_COMPLIANCE_MGR": [("read",""), ("write",""), ("approve",""), ("audit",""), ("export","")],
        "R_DIRECTOR":       [("read",""), ("write",""), ("approve",""), ("audit",""), ("export","")],
        "R_VP":             [("read",""), ("write",""), ("approve",""), ("audit",""), ("export","")],
        "R_MD":             [("read",""), ("write",""), ("execute",""), ("approve",""), ("audit",""), ("export","")],
        "R_INTERN":         [("read","")],
    }
    pa_rows = []
    for role, perms_list in role_perm_map.items():
        for perm, res_scope in perms_list:
            pa_rows.append({"role_id": role, "permission_id": perm, "resource_id": res_scope})
    role_permissions = pd.DataFrame(pa_rows)
    _save(role_permissions, base / "role_permissions.csv")

    print(f"  Fintech dataset saved to: {base}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large RBAC sample datasets")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    print(f"Generating datasets with seed={args.seed} ...")
    generate_hospital(args.seed)
    generate_university(args.seed)
    generate_fintech(args.seed)

    print("\n✓ All datasets generated successfully.")
    print("  Use them via: python scripts/run_demo.py  (update DATASET_DIR in script)")
    print("  Or upload directly at: http://localhost:5173")


if __name__ == "__main__":
    main()
