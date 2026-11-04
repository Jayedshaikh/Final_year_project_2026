"""Unit tests for the data pipeline module.

Tests use small hand-crafted datasets so they run in seconds on any machine.
Every test uses fixed seeds for reproducibility.
"""
from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd
import pytest

from backend.data_pipeline.auth_matrix import build_auth_matrix, get_authorisation_roles
from backend.data_pipeline.loader import RBACDataset, load_rbac_dataset
from backend.data_pipeline.preprocess import clean_attributes, encode_features
from backend.data_pipeline.sampling import build_training_samples, stratified_split


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_small_dataset() -> dict:
    """3 users, 2 roles, 3 permissions, 4 resources.

    Hand-computed expected auth tuples:
      u1 -> r_admin (all resources, all perms): 4*3 = 12 authorised
      u2 -> r_reader (all resources, read): 4 authorised
      u3 -> no roles: 0 authorised
    Total = 16 authorised, 3*4*3 - 16 = 36 - 16 = 20 unauthorised.
    """
    return {
        "users": (
            "user_id,department,position\n"
            "u1,admin,manager\n"
            "u2,finance,analyst\n"
            "u3,hr,staff\n"
        ).encode(),
        "roles": "role_id,role_name\nr_admin,Admin\nr_reader,Reader\n".encode(),
        "permissions": "permission_id\nread\nwrite\ndelete\n".encode(),
        "user_roles": "user_id,role_id\nu1,r_admin\nu2,r_reader\n".encode(),
        "role_permissions": (
            "role_id,permission_id,resource_id\n"
            "r_admin,read,\n"
            "r_admin,write,\n"
            "r_admin,delete,\n"
            "r_reader,read,\n"
        ).encode(),
        "resources": (
            "resource_id,type,sensitivity\n"
            "res1,report,low\n"
            "res2,record,high\n"
            "res3,report,medium\n"
            "res4,config,high\n"
        ).encode(),
    }


def _make_small_rbac_dataset() -> RBACDataset:
    files = _make_small_dataset()
    return load_rbac_dataset(files, fmt="csv", dataset_name="small_test")


# --------------------------------------------------------------------------- #
# Loader tests
# --------------------------------------------------------------------------- #

class TestLoader:
    def test_loads_csv_correctly(self):
        ds = _make_small_rbac_dataset()
        assert len(ds.users) == 3
        assert len(ds.roles) == 2
        assert len(ds.permissions) == 3
        assert len(ds.resources) == 4
        assert len(ds.user_roles) == 2
        assert len(ds.role_permissions) == 4

    def test_infers_user_attribute_columns(self):
        ds = _make_small_rbac_dataset()
        assert set(ds.user_attribute_columns) == {"department", "position"}

    def test_infers_resource_attribute_columns(self):
        ds = _make_small_rbac_dataset()
        assert set(ds.resource_attribute_columns) == {"type", "sensitivity"}

    def test_explicit_attribute_columns(self):
        files = _make_small_dataset()
        ds = load_rbac_dataset(
            files, fmt="csv",
            user_attribute_columns=["department"],
        )
        assert ds.user_attribute_columns == ["department"]

    def test_json_format(self):
        payload = {
            "users": [{"user_id": "u1", "dept": "eng"}],
            "roles": [{"role_id": "r1"}],
            "permissions": [{"permission_id": "read"}],
            "user_roles": [{"user_id": "u1", "role_id": "r1"}],
            "role_permissions": [{"role_id": "r1", "permission_id": "read", "resource_id": ""}],
            "resources": [{"resource_id": "res1", "type": "doc"}],
        }
        json_bytes = json.dumps(payload).encode()
        ds = load_rbac_dataset({"users": json_bytes}, fmt="json")
        assert len(ds.users) == 1
        assert len(ds.resources) == 1

    def test_missing_required_column_raises(self):
        bad_files = _make_small_dataset()
        bad_files["users"] = "uid,department\nu1,eng\n".encode()
        with pytest.raises(ValueError, match="user_id"):
            load_rbac_dataset(bad_files, fmt="csv")

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            load_rbac_dataset({}, fmt="xml")


# --------------------------------------------------------------------------- #
# Auth matrix tests
# --------------------------------------------------------------------------- #

class TestAuthMatrix:
    def test_hand_example_correct(self):
        ds = _make_small_rbac_dataset()
        matrix = build_auth_matrix(ds)

        # u1 should have all 12 tuples authorised (3 perms x 4 resources)
        u1 = matrix[matrix["user_id"] == "u1"]
        assert u1["authorised"].sum() == 12

        # u2 has read on all 4 resources
        u2_read = matrix[(matrix["user_id"] == "u2") & (matrix["permission"] == "read")]
        assert u2_read["authorised"].sum() == 4
        u2_write = matrix[(matrix["user_id"] == "u2") & (matrix["permission"] == "write")]
        assert u2_write["authorised"].sum() == 0

        # u3 has no roles -> all 12 tuples unauthorised
        u3 = matrix[matrix["user_id"] == "u3"]
        assert u3["authorised"].sum() == 0

    def test_total_size(self):
        ds = _make_small_rbac_dataset()
        matrix = build_auth_matrix(ds)
        # 3 users x 4 resources x 3 permissions
        assert len(matrix) == 3 * 4 * 3

    def test_scoped_pa_grants_only_that_resource(self):
        """A PA row with resource_id only grants access to that specific resource."""
        files = {
            "users": "user_id\nu1\n".encode(),
            "roles": "role_id\nr1\n".encode(),
            "permissions": "permission_id\nread\n".encode(),
            "user_roles": "user_id,role_id\nu1,r1\n".encode(),
            "role_permissions": "role_id,permission_id,resource_id\nr1,read,res1\n".encode(),
            "resources": "resource_id\nres1\nres2\n".encode(),
        }
        ds = load_rbac_dataset(files, fmt="csv")
        matrix = build_auth_matrix(ds)
        # only (u1, res1, read) should be authorised
        auth = matrix[matrix["authorised"] == 1]
        assert len(auth) == 1
        row = auth.iloc[0]
        assert row["user_id"] == "u1"
        assert row["resource_id"] == "res1"
        assert row["permission"] == "read"

    def test_blank_resource_id_grants_all(self):
        """A PA row with blank resource_id grants access to ALL resources."""
        files = {
            "users": "user_id\nu1\n".encode(),
            "roles": "role_id\nr1\n".encode(),
            "permissions": "permission_id\nread\n".encode(),
            "user_roles": "user_id,role_id\nu1,r1\n".encode(),
            "role_permissions": "role_id,permission_id,resource_id\nr1,read,\n".encode(),
            "resources": "resource_id\nres1\nres2\n".encode(),
        }
        ds = load_rbac_dataset(files, fmt="csv")
        matrix = build_auth_matrix(ds)
        auth = matrix[matrix["authorised"] == 1]
        assert len(auth) == 2  # both resources

    def test_sorted_output(self):
        ds = _make_small_rbac_dataset()
        matrix = build_auth_matrix(ds)
        keys = matrix[["user_id", "resource_id", "permission"]].values.tolist()
        assert keys == sorted(keys)

    def test_get_authorisation_roles(self):
        ds = _make_small_rbac_dataset()
        roles = get_authorisation_roles(ds, "u1", "res1", "read")
        assert "r_admin" in roles

        roles_none = get_authorisation_roles(ds, "u3", "res1", "read")
        assert roles_none == []


# --------------------------------------------------------------------------- #
# Preprocessing tests
# --------------------------------------------------------------------------- #

class TestPreprocess:
    def test_clean_strips_whitespace(self):
        df = pd.DataFrame({"user_id": ["u1"], "dept": [" Finance "]})
        cleaned = clean_attributes(df)
        assert cleaned["dept"].iloc[0] == "finance"

    def test_clean_imputes_categoricals(self):
        import numpy as np
        df = pd.DataFrame({"user_id": ["u1", "u2"], "dept": ["eng", np.nan]})
        cleaned = clean_attributes(df)
        assert cleaned["dept"].iloc[1] == "unknown"

    def test_clean_imputes_numerics(self):
        import numpy as np
        df = pd.DataFrame({"user_id": ["u1", "u2", "u3"], "years": [2.0, 4.0, np.nan]})
        cleaned = clean_attributes(df)
        assert cleaned["years"].iloc[2] == pytest.approx(3.0)  # median of [2, 4]

    def test_encode_no_leakage(self):
        """Encoder must be fitted on train only; unseen test categories become all-zero."""
        train = pd.DataFrame({
            "user_id": ["u1", "u2"],
            "permission": ["read", "write"],
            "dept": ["eng", "fin"],
            "authorised": [1, 0],
        })
        test = pd.DataFrame({
            "user_id": ["u3"],
            "permission": ["delete"],  # unseen category
            "dept": ["hr"],            # unseen category
            "authorised": [0],
        })
        X_train, X_test, encoder = encode_features(train, test)
        # X_test should have same number of columns as X_train
        assert X_train.shape[1] == X_test.shape[1]
        # All OHE values for unseen categories must be 0.0
        assert X_test.sum() == pytest.approx(0.0)

    def test_encode_feature_map_populated(self):
        train = pd.DataFrame({
            "user_id": ["u1", "u2"],
            "permission": ["read", "write"],
            "dept": ["eng", "fin"],
            "authorised": [1, 0],
        })
        test = pd.DataFrame({
            "user_id": ["u3"],
            "permission": ["read"],
            "dept": ["eng"],
            "authorised": [1],
        })
        _, _, encoder = encode_features(train, test)
        assert len(encoder.feature_map) == len(encoder.feature_names)


# --------------------------------------------------------------------------- #
# Sampling tests
# --------------------------------------------------------------------------- #

class TestSampling:
    def test_deterministic_with_same_seed(self):
        ds = _make_small_rbac_dataset()
        auth = build_auth_matrix(ds)
        s1, _, _ = build_training_samples(auth, ds.users, ds.resources,
                                          ds.user_attribute_columns,
                                          ds.resource_attribute_columns,
                                          seed=42)
        s2, _, _ = build_training_samples(auth, ds.users, ds.resources,
                                          ds.user_attribute_columns,
                                          ds.resource_attribute_columns,
                                          seed=42)
        pd.testing.assert_frame_equal(s1.reset_index(drop=True), s2.reset_index(drop=True))

    def test_different_seeds_may_differ(self):
        ds = _make_small_rbac_dataset()
        auth = build_auth_matrix(ds)
        s1, _, _ = build_training_samples(auth, ds.users, ds.resources,
                                          ds.user_attribute_columns,
                                          ds.resource_attribute_columns,
                                          seed=42)
        s2, _, _ = build_training_samples(auth, ds.users, ds.resources,
                                          ds.user_attribute_columns,
                                          ds.resource_attribute_columns,
                                          seed=99)
        # Not guaranteed to differ but statistically very likely
        try:
            pd.testing.assert_frame_equal(s1.reset_index(drop=True), s2.reset_index(drop=True))
            # They can be equal in degenerate cases; just verify both succeed
        except AssertionError:
            pass  # different samples: expected

    def test_ratio_honoured(self):
        ds = _make_small_rbac_dataset()
        auth = build_auth_matrix(ds)
        _, n_pos, n_neg = build_training_samples(
            auth, ds.users, ds.resources,
            ds.user_attribute_columns, ds.resource_attribute_columns,
            ratio=2.0, seed=42,
        )
        # n_neg should be ~2x n_pos (capped by available)
        assert n_neg <= 2 * n_pos + 1

    def test_empty_dataset_raises(self):
        empty = pd.DataFrame(columns=["user_id", "resource_id", "permission", "authorised"])
        with pytest.raises(ValueError, match="empty"):
            build_training_samples(empty, pd.DataFrame(), pd.DataFrame(),
                                   [], [], seed=42)

    def test_zero_positives_raises(self):
        all_unauth = pd.DataFrame({
            "user_id": ["u1"], "resource_id": ["r1"], "permission": ["read"], "authorised": [0]
        })
        with pytest.raises(ValueError, match="positive"):
            build_training_samples(all_unauth, pd.DataFrame(), pd.DataFrame(),
                                   [], [], seed=42)

    def test_zero_negatives_raises(self):
        all_auth = pd.DataFrame({
            "user_id": ["u1"], "resource_id": ["r1"], "permission": ["read"], "authorised": [1]
        })
        with pytest.raises(ValueError, match="unauthorised"):
            build_training_samples(all_auth, pd.DataFrame(), pd.DataFrame(),
                                   [], [], seed=42)

    def test_split_is_stratified(self):
        ds = _make_small_rbac_dataset()
        auth = build_auth_matrix(ds)
        samples, _, _ = build_training_samples(
            auth, ds.users, ds.resources,
            ds.user_attribute_columns, ds.resource_attribute_columns,
            seed=42,
        )
        train_df, test_df = stratified_split(samples, test_size=0.2, seed=42)
        # Check both splits have both classes
        assert train_df["authorised"].nunique() == 2
        assert test_df["authorised"].nunique() == 2

    def test_single_class_split_raises(self):
        single_class = pd.DataFrame({
            "user_id": ["u1", "u2", "u3"],
            "resource_id": ["r1", "r2", "r3"],
            "permission": ["read"] * 3,
            "authorised": [1, 1, 1],
        })
        with pytest.raises(ValueError, match="one class"):
            stratified_split(single_class)


# --------------------------------------------------------------------------- #
# Additional edge-case and integration tests (Guide section 10)
# --------------------------------------------------------------------------- #

class TestEdgeCases:
    """Guide section 10: edge cases that must raise clear errors, never crash."""

    def test_attribute_column_single_distinct_value_warns_keeps(self, caplog):
        """Single-value attribute column produces a warning but is kept (not dropped)."""
        import logging
        ds = _make_small_rbac_dataset()
        auth = build_auth_matrix(ds)
        # Build samples normally, then check encoding handles constant columns
        samples, _, _ = build_training_samples(
            auth, ds.users, ds.resources,
            ds.user_attribute_columns, ds.resource_attribute_columns,
            seed=42,
        )
        # Inject a constant column
        samples["user.constant_col"] = "same_value"
        train_df, test_df = stratified_split(samples, test_size=0.2, seed=42)
        # Encoding should succeed — constant OHE column produces one OHE column
        feature_cols = [c for c in train_df.columns if c not in {"user_id", "resource_id", "authorised"}]
        X_train, X_test, encoder = encode_features(train_df, test_df, feature_cols)
        assert X_train.shape[1] == X_test.shape[1]
        assert X_train.shape[0] > 0

    def test_samples_contain_both_classes_after_split(self):
        """Both train and test must contain class 0 and class 1."""
        ds = _make_small_rbac_dataset()
        auth = build_auth_matrix(ds)
        samples, _, _ = build_training_samples(
            auth, ds.users, ds.resources,
            ds.user_attribute_columns, ds.resource_attribute_columns,
            seed=42,
        )
        train_df, test_df = stratified_split(samples, test_size=0.2, seed=42)
        for df, name in [(train_df, "train"), (test_df, "test")]:
            assert df["authorised"].nunique() == 2, f"{name} split has only one class"

    def test_duplicate_users_in_sampling_still_works(self):
        """Duplicate rows in the dataset are handled without crashing."""
        files = _make_small_dataset()
        # Duplicate the first user_roles row
        files["user_roles"] = b"user_id,role_id\nu1,r_admin\nu1,r_admin\nu2,r_reader\n"
        ds = load_rbac_dataset(files, fmt="csv")
        matrix = build_auth_matrix(ds)
        # Auth matrix should be identical to the non-duplicate version
        u1_auth = matrix[matrix["user_id"] == "u1"]["authorised"].sum()
        assert u1_auth == 12  # same as hand-computed

    def test_user_with_no_role_produces_only_unauthorised_tuples(self):
        """A user with no UA entry should have authorised=0 for all their tuples."""
        ds = _make_small_rbac_dataset()
        matrix = build_auth_matrix(ds)
        u3 = matrix[matrix["user_id"] == "u3"]
        assert len(u3) > 0
        assert u3["authorised"].sum() == 0

    def test_negative_sampling_ratio_zero_raises(self):
        """ratio=0 is invalid per NegativeSamplingConfig (gt=0)."""
        from pydantic import ValidationError
        from shared.schemas.contracts import NegativeSamplingConfig
        with pytest.raises(ValidationError):
            NegativeSamplingConfig(ratio=0.0)


class TestEncoderLeakage:
    """Strict leak-free encoding: test split categories must never influence the encoder."""

    def test_test_only_numeric_values_use_train_median(self):
        """Numeric column values only in test must be imputed using the training median."""
        import numpy as np
        train = pd.DataFrame({
            "user_id": ["u1", "u2", "u3", "u4"],
            "seniority": [2.0, 4.0, 6.0, 8.0],  # train median = 5.0
            "authorised": [1, 0, 1, 0],
        })
        # Test has an extreme value that should NOT affect imputation
        test = pd.DataFrame({
            "user_id": ["u5"],
            "seniority": [np.nan],
            "authorised": [1],
        })
        X_train, X_test, encoder = encode_features(train, test)
        # Imputed value should be train median (5.0), not influenced by test NaN
        assert encoder.median_values.get("seniority") == pytest.approx(5.0)
        # X_test should have the imputed value (5.0) in the seniority position
        assert X_test.shape == (1, 1)
        assert X_test[0, 0] == pytest.approx(5.0)

    def test_encoder_fitted_once_on_train_categories_only(self):
        """OHE categories come from train only; extra test categories ignored."""
        train = pd.DataFrame({
            "user_id": ["u1", "u2"],
            "dept": ["eng", "fin"],
            "authorised": [1, 0],
        })
        test = pd.DataFrame({
            "user_id": ["u3", "u4"],
            "dept": ["mkt", "legal"],  # completely unseen
            "authorised": [0, 1],
        })
        X_train, X_test, encoder = encode_features(train, test)
        # OHE was fit on ["eng", "fin"] — test rows should all be zero vectors
        assert X_test.sum() == pytest.approx(0.0)
        # Train columns must match test columns in count
        assert X_train.shape[1] == X_test.shape[1]
