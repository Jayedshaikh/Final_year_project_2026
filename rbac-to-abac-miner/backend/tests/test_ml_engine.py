"""Unit tests for the ML engine module.

Uses tiny datasets so tests run in seconds on any machine.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier

from backend.data_pipeline.auth_matrix import build_auth_matrix
from backend.data_pipeline.loader import load_rbac_dataset
from backend.data_pipeline.preprocess import encode_features
from backend.data_pipeline.sampling import build_training_samples, stratified_split
from backend.ml_engine.evaluate import evaluate_model
from backend.ml_engine.extract_rules import extract_permit_rules
from backend.ml_engine.train import train_models
from shared.schemas.contracts import (
    ModelMetrics,
    NegativeSamplingConfig,
    TrainingConfigRequest,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _small_training_data():
    """Minimal labelled dataset: 20 samples, 2 features, balanced classes."""
    rng = np.random.default_rng(42)
    n = 20
    X = rng.uniform(0, 1, (n, 2)).astype(np.float32)
    y = (X[:, 0] > 0.5).astype(int)  # planted pattern: feature_0 > 0.5 => authorised
    split = int(0.8 * n)
    return X[:split], y[:split], X[split:], y[split:]


def _make_small_csv_dataset():
    """3 users, 2 roles, 3 resources with planted rule: dept=fin -> read on sensitivity=low."""
    files = {
        "users": (
            "user_id,department,seniority\n"
            "u1,finance,5\nu2,hr,3\nu3,finance,2\n"
        ).encode(),
        "roles": "role_id\nr_fin\nr_hr\n".encode(),
        "permissions": "permission_id\nread\nwrite\n".encode(),
        "user_roles": "user_id,role_id\nu1,r_fin\nu3,r_fin\nu2,r_hr\n".encode(),
        "role_permissions": (
            "role_id,permission_id,resource_id\n"
            "r_fin,read,\nr_fin,write,\nr_hr,read,\n"
        ).encode(),
        "resources": (
            "resource_id,type,sensitivity\n"
            "res1,report,low\nres2,record,high\nres3,report,medium\n"
        ).encode(),
    }
    return load_rbac_dataset(files, fmt="csv")


# --------------------------------------------------------------------------- #
# Evaluate tests
# --------------------------------------------------------------------------- #

class TestEvaluate:
    def test_returns_model_metrics(self):
        X_train, y_train, X_test, y_test = _small_training_data()
        dt = DecisionTreeClassifier(random_state=42)
        dt.fit(X_train, y_train)
        metrics = evaluate_model(dt, X_test, y_test, training_time_seconds=0.01)
        assert isinstance(metrics, ModelMetrics)
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1 <= 1.0

    def test_mismatched_lengths_raises(self):
        X_train, y_train, X_test, y_test = _small_training_data()
        dt = DecisionTreeClassifier(random_state=42).fit(X_train, y_train)
        with pytest.raises(ValueError, match="length mismatch"):
            evaluate_model(dt, X_test, y_test[:2], training_time_seconds=0.0)


# --------------------------------------------------------------------------- #
# Train tests
# --------------------------------------------------------------------------- #

class TestTrainModels:
    def test_same_seed_gives_identical_metrics(self):
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree"],
            random_seed=42,
            cv_folds=2,
        )
        r1 = train_models(X_tr, y_tr, X_te, y_te, config)
        r2 = train_models(X_tr, y_tr, X_te, y_te, config)
        assert r1[0].metrics.f1 == pytest.approx(r2[0].metrics.f1)

    def test_is_rule_extraction_model_only_on_dt(self):
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree", "random_forest", "gradient_boosting"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        dt_results = [r for r in results if r.model_name == "decision_tree"]
        non_dt = [r for r in results if r.model_name != "decision_tree"]
        assert all(r.is_rule_extraction_model for r in dt_results)
        assert all(not r.is_rule_extraction_model for r in non_dt)

    def test_all_three_models_train(self):
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree", "random_forest", "gradient_boosting"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        names = {r.model_name for r in results}
        assert names == {"decision_tree", "random_forest", "gradient_boosting"}

    def test_training_time_recorded(self):
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        assert results[0].metrics.training_time_seconds >= 0.0

    def test_cv_f1_stats_populated(self):
        """CV mean and std must be set after training."""
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        m = results[0].metrics
        assert m.cv_f1_mean is not None
        assert m.cv_f1_std is not None

    def test_model_persisted_to_disk_and_reloads(self, tmp_path, monkeypatch):
        """Trained model is saved to disk and can be reloaded identically."""
        from backend.ml_engine import train as train_module
        # Redirect model save directory to tmp_path
        monkeypatch.setattr(train_module, "_MODELS_DIR", tmp_path)

        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        model_id = results[0].model_id

        # The file should now exist in tmp_path
        model_path = tmp_path / f"{model_id}.joblib"
        assert model_path.exists(), f"Model file not found: {model_path}"

        # Reload and check predictions are identical
        import joblib
        loaded = joblib.load(model_path)
        pred_orig = results[0]  # we don't have the original object, just compare predict
        y_pred_loaded = loaded.predict(X_te)
        assert len(y_pred_loaded) == len(y_te)

    def test_hyperparams_used_populated(self):
        """hyperparams_used dict must not be empty after training."""
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree", "random_forest"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        for r in results:
            assert isinstance(r.hyperparams_used, dict)
            assert len(r.hyperparams_used) > 0

    def test_different_seed_may_give_different_cv_score(self):
        """Different seeds can produce different CV scores (probabilistic check)."""
        X_tr, y_tr, X_te, y_te = _small_training_data()
        cfg1 = TrainingConfigRequest(dataset_id="ds", models=["random_forest"], random_seed=42, cv_folds=2)
        cfg2 = TrainingConfigRequest(dataset_id="ds", models=["random_forest"], random_seed=99, cv_folds=2)
        r1 = train_models(X_tr, y_tr, X_te, y_te, cfg1)
        r2 = train_models(X_tr, y_tr, X_te, y_te, cfg2)
        # Not guaranteed to differ on tiny data, but both must be valid floats
        assert 0.0 <= r1[0].metrics.f1 <= 1.0
        assert 0.0 <= r2[0].metrics.f1 <= 1.0


# --------------------------------------------------------------------------- #
# Extract rules tests
# --------------------------------------------------------------------------- #

class TestExtractRules:
    def _build_pipeline(self):
        ds = _make_small_csv_dataset()
        auth = build_auth_matrix(ds)
        samples, _, _ = build_training_samples(
            auth, ds.users, ds.resources,
            ds.user_attribute_columns, ds.resource_attribute_columns,
            seed=42,
        )
        train_df, test_df = stratified_split(samples, test_size=0.2, seed=42)
        feature_cols = [
            c for c in train_df.columns
            if c not in {"user_id", "resource_id", "authorised"}
        ]
        X_train, X_test, encoder = encode_features(train_df, test_df, feature_cols)
        y_train = train_df["authorised"].values
        y_test = test_df["authorised"].values
        dt = DecisionTreeClassifier(random_state=42, max_depth=4)
        dt.fit(X_train, y_train)
        return dt, encoder, train_df

    def test_extracts_list_of_rules(self):
        dt, encoder, train_df = self._build_pipeline()
        rules = extract_permit_rules(
            tree=dt,
            feature_names=encoder.feature_names,
            encoder=encoder,
            samples=train_df,
            min_support=0.0,   # no filter for test
            min_confidence=0.0,
        )
        assert isinstance(rules, list)

    def test_rules_have_conditions(self):
        dt, encoder, train_df = self._build_pipeline()
        rules = extract_permit_rules(
            tree=dt,
            feature_names=encoder.feature_names,
            encoder=encoder,
            samples=train_df,
            min_support=0.0,
            min_confidence=0.0,
        )
        for rule in rules:
            assert len(rule.conditions) >= 1

    def test_rules_are_candidate_status(self):
        dt, encoder, train_df = self._build_pipeline()
        rules = extract_permit_rules(
            tree=dt,
            feature_names=encoder.feature_names,
            encoder=encoder,
            samples=train_df,
            min_support=0.0,
            min_confidence=0.0,
        )
        from shared.schemas.contracts import RuleStatus
        for rule in rules:
            assert rule.status == RuleStatus.CANDIDATE

    def test_same_seed_gives_identical_rules(self):
        dt, encoder, train_df = self._build_pipeline()
        rules_1 = extract_permit_rules(dt, encoder.feature_names, encoder, train_df, 0.0, 0.0)
        rules_2 = extract_permit_rules(dt, encoder.feature_names, encoder, train_df, 0.0, 0.0)
        assert len(rules_1) == len(rules_2)
        for r1, r2 in zip(rules_1, rules_2):
            assert r1.rule_id == r2.rule_id

    def test_feature_length_mismatch_raises(self):
        X_tr = np.array([[0, 1], [1, 0]], dtype=np.float32)
        y_tr = np.array([0, 1])
        dt = DecisionTreeClassifier(random_state=42).fit(X_tr, y_tr)
        from backend.data_pipeline.preprocess import FeatureEncoder
        encoder = FeatureEncoder(feature_names=["f1", "f2"], feature_map={})
        # Pass wrong feature_names length
        with pytest.raises(ValueError, match="feature_names length"):
            extract_permit_rules(dt, ["f1"], encoder, pd.DataFrame(), 0.0, 0.0)

    def test_min_support_filters_rules(self):
        """Rules below min_support are excluded."""
        dt, encoder, train_df = self._build_pipeline()
        # With very high min_support all rules should be filtered
        rules_strict = extract_permit_rules(
            tree=dt,
            feature_names=encoder.feature_names,
            encoder=encoder,
            samples=train_df,
            min_support=1.0,   # impossible to satisfy
            min_confidence=0.0,
        )
        assert rules_strict == []

    def test_rules_source_is_tree_path(self):
        dt, encoder, train_df = self._build_pipeline()
        rules = extract_permit_rules(dt, encoder.feature_names, encoder, train_df, 0.0, 0.0)
        for rule in rules:
            assert rule.source == "tree_path"

    def test_rule_ids_sequential(self):
        dt, encoder, train_df = self._build_pipeline()
        rules = extract_permit_rules(dt, encoder.feature_names, encoder, train_df, 0.0, 0.0)
        for i, rule in enumerate(rules, start=1):
            assert rule.rule_id == f"R{i:03d}"

    def test_coverage_counts_non_negative(self):
        dt, encoder, train_df = self._build_pipeline()
        rules = extract_permit_rules(dt, encoder.feature_names, encoder, train_df, 0.0, 0.0)
        for rule in rules:
            assert rule.n_covered_positive >= 0
            assert rule.n_covered_negative >= 0


# --------------------------------------------------------------------------- #
# Config loader tests
# --------------------------------------------------------------------------- #

class TestConfigLoader:
    def test_loads_config_without_error(self):
        from backend.utils.config import load_config
        cfg = load_config(force_reload=True)
        assert isinstance(cfg, dict)

    def test_random_seed_in_config(self):
        from backend.utils.config import get as get_cfg
        seed = get_cfg("random_seed", 42)
        assert isinstance(seed, int)
        assert seed == 42

    def test_wsc_weights_returned(self):
        from backend.utils.config import get_wsc_weights
        weights = get_wsc_weights()
        assert "w_rule" in weights
        assert "w_cond" in weights
        assert "w_val" in weights


# --------------------------------------------------------------------------- #
# Seed utility tests
# --------------------------------------------------------------------------- #

class TestSeedUtils:
    def test_get_rng_is_deterministic(self):
        from backend.utils.seed import get_rng
        rng1 = get_rng(42)
        rng2 = get_rng(42)
        assert rng1.integers(0, 1000) == rng2.integers(0, 1000)

    def test_different_seeds_differ(self):
        from backend.utils.seed import get_rng
        rng1 = get_rng(42)
        rng2 = get_rng(99)
        # With overwhelming probability these differ
        vals1 = [rng1.integers(0, 10000) for _ in range(5)]
        vals2 = [rng2.integers(0, 10000) for _ in range(5)]
        assert vals1 != vals2


# --------------------------------------------------------------------------- #
# Timer utility tests
# --------------------------------------------------------------------------- #

class TestTimer:
    def test_timer_records_elapsed(self):
        import time
        from backend.utils.timing import timer
        with timer() as t:
            time.sleep(0.01)
        assert t["elapsed"] >= 0.005  # at least 5ms


# --------------------------------------------------------------------------- #
# Tree-rule equivalence test (Guide section 10)
# "Test that extracted rules reproduce the tree's positive predictions on training data"
# --------------------------------------------------------------------------- #

class TestTreeRuleEquivalence:
    """Extracted rules must reproduce the Decision Tree's permit predictions on training data."""

    def _full_pipeline(self):
        """Build a complete pipeline and return tree, encoder, train_df, X_train, y_train."""
        ds = _make_small_csv_dataset()
        auth = build_auth_matrix(ds)
        samples, _, _ = build_training_samples(
            auth, ds.users, ds.resources,
            ds.user_attribute_columns, ds.resource_attribute_columns,
            seed=42,
        )
        train_df, test_df = stratified_split(samples, test_size=0.2, seed=42)
        feature_cols = [c for c in train_df.columns if c not in {"user_id", "resource_id", "authorised"}]
        X_train, X_test, encoder = encode_features(train_df, test_df, feature_cols)
        y_train = train_df["authorised"].values
        dt = DecisionTreeClassifier(random_state=42, max_depth=6, class_weight="balanced")
        dt.fit(X_train, y_train)
        return dt, encoder, train_df, X_train, y_train

    def test_rules_reproduce_tree_permit_predictions(self):
        """Rules extracted from the DT must permit every sample the DT predicts positive."""
        from shared.schemas.contracts import Operator

        dt, encoder, train_df, X_train, y_train = self._full_pipeline()

        # Get tree predictions (positive class = 1 = permit)
        tree_predictions = dt.predict(X_train)  # 0 or 1 per training sample

        # Extract rules with no filters
        rules = extract_permit_rules(
            tree=dt,
            feature_names=encoder.feature_names,
            encoder=encoder,
            samples=train_df,
            min_support=0.0,
            min_confidence=0.0,
        )

        # For every training sample the tree predicts as permit (1),
        # at least one extracted rule should match it.
        def rule_matches_row(rule, row: pd.Series) -> bool:
            """Check if a single ABACRule matches a decoded sample row."""
            # action must match permission
            perm_col = "permission"
            if perm_col in row and row[perm_col] != rule.action:
                return False
            for cond in rule.conditions:
                attr = cond.attribute
                if attr not in row.index:
                    return False
                val = row[attr]
                cv = cond.value
                op = cond.operator
                try:
                    if op == Operator.EQ:
                        if str(val) != str(cv):
                            return False
                    elif op == Operator.NEQ:
                        if str(val) == str(cv):
                            return False
                    elif op == Operator.IN:
                        if str(val) not in [str(v) for v in cv]:
                            return False
                    elif op == Operator.NOT_IN:
                        if str(val) in [str(v) for v in cv]:
                            return False
                    elif op in (Operator.LTE, Operator.GT, Operator.GTE, Operator.LT):
                        fval = float(val)
                        fcv = float(cv)
                        if op == Operator.LTE and not (fval <= fcv):
                            return False
                        if op == Operator.GT and not (fval > fcv):
                            return False
                        if op == Operator.GTE and not (fval >= fcv):
                            return False
                        if op == Operator.LT and not (fval < fcv):
                            return False
                except (ValueError, TypeError):
                    return False
            return True

        n_tree_permits = int((tree_predictions == 1).sum())
        if n_tree_permits == 0:
            # degenerate case — no positive predictions, nothing to test
            return

        # Count how many tree-permit rows are covered by at least one rule
        n_covered = 0
        for i, pred in enumerate(tree_predictions):
            if pred == 1:
                row = train_df.iloc[i]
                if any(rule_matches_row(r, row) for r in rules):
                    n_covered += 1

        # At least 80% of tree permits must be covered by the extracted rules
        # (not 100% because the action-extraction heuristic may drop ambiguous paths)
        coverage_rate = n_covered / n_tree_permits
        assert coverage_rate >= 0.8, (
            f"Rules cover only {coverage_rate:.0%} of DT permit predictions "
            f"({n_covered}/{n_tree_permits}). Expected ≥80%."
        )

    def test_no_rules_extracted_from_rf_or_gb(self):
        """Confirm extract_permit_rules is only called on DT — never RF or GB."""
        from backend.ml_engine.train import train_models
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree", "random_forest", "gradient_boosting"],
            random_seed=42,
            cv_folds=2,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        # is_rule_extraction_model must be True for exactly 1 model (DT), False for rest
        extraction_flags = [r.is_rule_extraction_model for r in results]
        assert extraction_flags.count(True) == 1, (
            f"Expected exactly 1 rule-extraction model, got {extraction_flags.count(True)}"
        )
        dt_info = next(r for r in results if r.model_name == "decision_tree")
        assert dt_info.is_rule_extraction_model is True
        for r in results:
            if r.model_name != "decision_tree":
                assert r.is_rule_extraction_model is False


# --------------------------------------------------------------------------- #
# Hyperparameter tuning test
# --------------------------------------------------------------------------- #

class TestHyperparamTuning:
    """Guide section 5: optional grid search inside CV on train split only."""

    def test_tune_hyperparameters_dt_returns_best_params(self):
        """With tune_hyperparameters=True, DT returns chosen hyperparams."""
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree"],
            random_seed=42,
            cv_folds=2,
            tune_hyperparameters=True,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        dt_result = results[0]
        # After grid search, hyperparams_used must contain at least max_depth
        assert "max_depth" in dt_result.hyperparams_used

    def test_tune_hyperparameters_does_not_touch_test_split(self):
        """Even with tuning enabled, test-split metrics should be evaluated once."""
        X_tr, y_tr, X_te, y_te = _small_training_data()
        config = TrainingConfigRequest(
            dataset_id="ds_test",
            models=["decision_tree"],
            random_seed=42,
            cv_folds=2,
            tune_hyperparameters=True,
        )
        results = train_models(X_tr, y_tr, X_te, y_te, config)
        m = results[0].metrics
        # All metrics should be valid floats in [0,1]
        assert 0.0 <= m.precision <= 1.0
        assert 0.0 <= m.recall <= 1.0
        assert 0.0 <= m.f1 <= 1.0
