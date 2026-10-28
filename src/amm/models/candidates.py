"""Candidate model pipelines.

Every candidate is a complete scikit-learn pipeline (preprocessing + model),
fitted only on the rows it is given. All models predict log1p(count) and are
wrapped so callers always receive non-negative counts.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from amm.data.features import CATEGORICAL, FEATURES

NUMERIC = [c for c in FEATURES if c not in CATEGORICAL]

# Small, fixed configurations (bounded search; documented in docs/EVALUATION.md)
DEFAULT_PARAMS = {
    "ridge": {"alpha": 3.0},
    "rf": {"n_estimators": 80, "min_samples_leaf": 4, "max_features": 0.6, "n_jobs": 2},
    "hgb": {"max_iter": 250, "learning_rate": 0.06, "max_leaf_nodes": 31, "l2_regularization": 1.0},
}


def _add_hour_daytype(X):
    X = X.copy()
    X["hr_wd"] = X["hr"].astype(int) + 24 * X["workingday"].astype(int)
    return X


def _ridge(seed: int, params: dict):
    cat = ["hr_wd", "weekday", "mnth", "weathersit"]
    num = [c for c in NUMERIC if c not in ("workingday",)] + ["workingday"]
    pre = ColumnTransformer(
        [
            ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), cat),
            ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), num),
        ]
    )
    return Pipeline(
        [("hour_daytype", FunctionTransformer(_add_hour_daytype)), ("pre", pre), ("model", Ridge(alpha=params["alpha"]))]
    )


def _rf(seed: int, params: dict):
    pre = ColumnTransformer([("all", SimpleImputer(strategy="median"), FEATURES)])
    return Pipeline([("pre", pre), ("model", RandomForestRegressor(random_state=seed, **params))])


def _hgb(seed: int, params: dict):
    # HGB handles missing values natively; categorical features are declared by name.
    pre = ColumnTransformer([("all", "passthrough", FEATURES)], verbose_feature_names_out=False)
    pre.set_output(transform="pandas")
    model = HistGradientBoostingRegressor(
        random_state=seed, categorical_features=["hr", "weekday", "season"], early_stopping=False, **params
    )
    return Pipeline([("pre", pre), ("model", model)])


BUILDERS = {"ridge": _ridge, "rf": _rf, "hgb": _hgb}


class CountRegressor(BaseEstimator, RegressorMixin):
    """Wrap a log1p-target pipeline; predictions are clipped to >= 0."""

    def __init__(self, inner=None):
        self.inner = inner

    def fit(self, X, y):
        self.model_ = TransformedTargetRegressor(regressor=clone(self.inner), func=np.log1p, inverse_func=np.expm1)
        self.model_.fit(X[FEATURES], np.asarray(y, dtype=float))
        return self

    def predict(self, X):
        return np.clip(self.model_.predict(X[FEATURES]), 0.0, None)


class ScaledModel(BaseEstimator, RegressorMixin):
    """TEST-ONLY fault injection: an otherwise valid model whose predictions are
    multiplied by ``factor``. Used to demonstrate rejection/rollback honestly."""

    def __init__(self, base=None, factor: float = 0.5):
        self.base = base
        self.factor = factor

    def fit(self, X, y):
        self.base_ = clone(self.base).fit(X, y)
        return self

    def predict(self, X):
        return self.base_.predict(X) * self.factor


def make_model(name: str, seed: int = 0, params: dict | None = None):
    if name.startswith("weak_"):
        # e.g. weak_hgb: deliberately miscalibrated version of a real model
        return ScaledModel(base=make_model(name[len("weak_"):], seed, params), factor=0.45)
    p = dict(DEFAULT_PARAMS[name])
    p.update(params or {})
    return CountRegressor(inner=BUILDERS[name](seed, p))
