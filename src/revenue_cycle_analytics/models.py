from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class ModelOutputs:
    metrics: dict[str, object]
    claim_scores: pd.DataFrame
    appeal_priority_scores: pd.DataFrame
    feature_importance: pd.DataFrame


def train_and_score_models(tables: dict[str, pd.DataFrame], output_dir: Path) -> ModelOutputs:
    output_dir.mkdir(parents=True, exist_ok=True)
    claim_model = _train_denial_risk_model(tables)
    appeal_model = _train_appeal_success_model(tables)

    metrics = {
        "denial_risk_model": claim_model["metrics"],
        "appeal_success_model": appeal_model["metrics"],
    }
    importance_frames = [
        claim_model["feature_importance"].assign(model_name="denial_risk_model"),
        appeal_model["feature_importance"].assign(model_name="appeal_success_model"),
    ]
    importance_frames = [frame for frame in importance_frames if not frame.empty]
    feature_importance = (
        pd.concat(importance_frames, ignore_index=True)
        if importance_frames
        else pd.DataFrame(columns=["feature", "importance", "model_name"])
    )

    claim_scores = claim_model["scores"]
    appeal_scores = appeal_model["scores"]
    claim_scores.to_csv(output_dir / "model_claim_denial_scores.csv", index=False)
    appeal_scores.to_csv(output_dir / "model_appeal_priority_scores.csv", index=False)
    feature_importance.to_csv(output_dir / "model_feature_importance.csv", index=False)
    (output_dir / "model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return ModelOutputs(metrics=metrics, claim_scores=claim_scores, appeal_priority_scores=appeal_scores, feature_importance=feature_importance)


def _one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def _make_preprocessor(categorical_features: list[str], numeric_features: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", _one_hot_encoder()),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_features),
            ("cat", categorical_pipe, categorical_features),
        ],
        remainder="drop",
    )


def _train_denial_risk_model(tables: dict[str, pd.DataFrame]) -> dict[str, object]:
    data = _claim_feature_frame(tables)
    target = data["denied_flag"].astype(int)
    feature_cols = [
        "issuer_name",
        "plan_name",
        "metal_level",
        "network_type",
        "service_line",
        "claim_type",
        "network_status",
        "member_risk_segment",
        "submitted_amount",
        "allowed_amount",
        "expected_payment_amount",
        "prior_auth_required_flag",
        "prior_auth_present_flag",
        "documentation_required_flag",
        "documentation_present_flag",
        "timely_filing_flag",
        "duplicate_claim_flag",
        "benchmark_denial_rate",
    ]
    categorical = [
        "issuer_name",
        "plan_name",
        "metal_level",
        "network_type",
        "service_line",
        "claim_type",
        "network_status",
        "member_risk_segment",
    ]
    numeric = [col for col in feature_cols if col not in categorical]
    X = _coerce_model_features(data[feature_cols], categorical, numeric)
    model = Pipeline(
        steps=[
            ("preprocess", _make_preprocessor(categorical, numeric)),
            ("model", RandomForestClassifier(n_estimators=220, min_samples_leaf=18, random_state=17, class_weight="balanced_subsample")),
        ]
    )
    X_train, X_test, y_train, y_test = _safe_train_test_split(X, target, random_state=17)
    model.fit(X_train, y_train)
    test_scores = model.predict_proba(X_test)[:, 1]
    all_scores = model.predict_proba(X)[:, 1]
    metrics = _classification_metrics(y_test, test_scores)
    metrics.update(
        {
            "model_type": "RandomForestClassifier",
            "rows_trained": int(len(X_train)),
            "rows_tested": int(len(X_test)),
            "positive_rate": round(float(target.mean()), 4),
        }
    )
    scores = data[
        [
            "claim_key",
            "claim_id",
            "issuer_name",
            "plan_name",
            "service_line",
            "network_status",
            "submitted_amount",
            "expected_payment_amount",
            "denied_flag",
        ]
    ].copy()
    scores["denial_risk_score"] = all_scores.round(4)
    scores["risk_tier"] = pd.qcut(scores["denial_risk_score"].rank(method="first"), 4, labels=["Low", "Medium", "High", "Critical"])
    scores["recommended_prebill_action"] = np.select(
        [
            data["prior_auth_required_flag"].astype(bool) & ~data["prior_auth_present_flag"].astype(bool),
            data["documentation_required_flag"].astype(bool) & ~data["documentation_present_flag"].astype(bool),
            data["timely_filing_flag"].astype(bool).eq(False),
            data["network_status"].eq("Out-of-network"),
        ],
        [
            "Check authorization",
            "Attach documentation",
            "Late filing review",
            "Network exception review",
        ],
        default="Pre-bill analyst review",
    )
    return {
        "metrics": metrics,
        "scores": scores.sort_values("denial_risk_score", ascending=False),
        "feature_importance": _feature_importance(model, categorical, numeric),
    }


def _train_appeal_success_model(tables: dict[str, pd.DataFrame]) -> dict[str, object]:
    data = _appeal_feature_frame(tables)
    denials_to_score = _denial_scoring_frame(tables)
    feature_cols = [
        "issuer_name",
        "plan_name",
        "service_line",
        "network_status",
        "denial_reason_category",
        "preventable_flag",
        "appealable_flag",
        "denied_amount",
        "expected_recovery_probability",
        "days_to_denial",
        "days_to_appeal",
    ]
    categorical = ["issuer_name", "plan_name", "service_line", "network_status", "denial_reason_category"]
    numeric = [col for col in feature_cols if col not in categorical]

    if data.empty or data["appeal_success_flag"].nunique() < 2 or len(data) < 80:
        scored = _baseline_appeal_scores(denials_to_score)
        metrics = {
            "model_type": "Reason-code baseline",
            "rows_trained": int(len(data)),
            "rows_tested": 0,
            "roc_auc": None,
            "average_precision": None,
            "precision_at_top_decile": None,
            "recall_at_top_decile": None,
            "positive_rate": float(data["appeal_success_flag"].mean()) if not data.empty else 0.0,
            "note": "Fallback used because appeal sample did not contain enough class variation.",
        }
        return {
            "metrics": metrics,
            "scores": scored,
            "feature_importance": pd.DataFrame(columns=["feature", "importance"]),
        }

    target = data["appeal_success_flag"].astype(int)
    X = _coerce_model_features(data[feature_cols], categorical, numeric)
    score_X = _coerce_model_features(denials_to_score[feature_cols], categorical, numeric)
    model = Pipeline(
        steps=[
            ("preprocess", _make_preprocessor(categorical, numeric)),
            ("model", RandomForestClassifier(n_estimators=180, min_samples_leaf=10, random_state=23, class_weight="balanced_subsample")),
        ]
    )
    X_train, X_test, y_train, y_test = _safe_train_test_split(X, target, random_state=23)
    model.fit(X_train, y_train)
    test_scores = model.predict_proba(X_test)[:, 1]
    all_scores = model.predict_proba(score_X)[:, 1]
    metrics = _classification_metrics(y_test, test_scores)
    metrics.update(
        {
            "model_type": "RandomForestClassifier",
            "rows_trained": int(len(X_train)),
            "rows_tested": int(len(X_test)),
            "positive_rate": round(float(target.mean()), 4),
        }
    )
    scored = denials_to_score[
        [
            "denial_key",
            "claim_id",
            "issuer_name",
            "plan_name",
            "service_line",
            "denial_reason_category",
            "denied_amount",
            "recoverable_amount",
            "expected_recovery_probability",
            "expected_recovery_value",
            "priority_score",
        ]
    ].copy()
    scored["appeal_success_probability"] = all_scores.round(4)
    scored["model_expected_recovery_value"] = (scored["recoverable_amount"] * scored["appeal_success_probability"]).round(2)
    scored["priority_rank"] = scored["model_expected_recovery_value"].rank(ascending=False, method="first").astype(int)
    return {
        "metrics": metrics,
        "scores": scored.sort_values("priority_rank"),
        "feature_importance": _feature_importance(model, categorical, numeric),
    }


def _claim_feature_frame(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    claim = tables["fact_claim"].copy()
    return (
        claim.merge(tables["dim_issuer"][["issuer_key", "issuer_name"]], on="issuer_key", how="left")
        .merge(tables["dim_plan"][["plan_key", "plan_name", "metal_level", "network_type"]], on="plan_key", how="left")
        .merge(tables["dim_service"][["service_key", "service_line"]], on="service_key", how="left", suffixes=("", "_dim"))
    )


def _appeal_feature_frame(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    appeals = tables["fact_appeal"]
    if appeals.empty:
        return pd.DataFrame()
    base = _denial_scoring_frame(tables).drop(columns=["days_to_appeal"], errors="ignore")
    return base.merge(
        appeals[["denial_key", "days_to_appeal", "appeal_success_flag"]],
        on="denial_key",
        how="inner",
    )


def _denial_scoring_frame(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    denial = tables["fact_denial"]
    claim = tables["fact_claim"]
    leakage = tables["fact_revenue_leakage"]
    reason = tables["dim_denial_reason"]
    frame = (
        denial.merge(reason[["denial_reason_key", "denial_reason_category"]], on="denial_reason_key", how="left")
        .merge(claim[["claim_key", "claim_id", "issuer_key", "plan_key", "service_key", "network_status"]], on="claim_key", how="left")
        .merge(tables["dim_issuer"][["issuer_key", "issuer_name"]], on="issuer_key", how="left")
        .merge(tables["dim_plan"][["plan_key", "plan_name"]], on="plan_key", how="left")
        .merge(tables["dim_service"][["service_key", "service_line"]], on="service_key", how="left")
        .merge(leakage[["denial_key", "recoverable_amount", "expected_recovery_probability", "expected_recovery_value", "priority_score"]], on="denial_key", how="left")
    )
    frame["days_to_appeal"] = 14
    return frame


def _coerce_model_features(frame: pd.DataFrame, categorical: list[str], numeric: list[str]) -> pd.DataFrame:
    output = frame.copy()
    for col in categorical:
        output[col] = output[col].astype("object").fillna("Unknown")
    for col in numeric:
        output[col] = pd.to_numeric(output[col], errors="coerce")
    return output


def _safe_train_test_split(X: pd.DataFrame, y: pd.Series, random_state: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    stratify = y if y.nunique() > 1 and y.value_counts().min() >= 2 else None
    test_size = 0.25
    if stratify is not None:
        test_size = max(test_size, min(0.5, y.nunique() / len(y)))
    return train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=stratify)


def _classification_metrics(y_true: pd.Series, scores: np.ndarray) -> dict[str, float | None]:
    if y_true.nunique() < 2:
        return {
            "roc_auc": None,
            "average_precision": None,
            "precision_at_top_decile": None,
            "recall_at_top_decile": None,
        }
    threshold = np.quantile(scores, 0.90)
    top = scores >= threshold
    positives = y_true.to_numpy() == 1
    precision = float(positives[top].mean()) if top.any() else 0.0
    recall = float(positives[top].sum() / positives.sum()) if positives.sum() else 0.0
    return {
        "roc_auc": round(float(roc_auc_score(y_true, scores)), 4),
        "average_precision": round(float(average_precision_score(y_true, scores)), 4),
        "precision_at_top_decile": round(precision, 4),
        "recall_at_top_decile": round(recall, 4),
    }


def _feature_importance(model: Pipeline, categorical: list[str], numeric: list[str]) -> pd.DataFrame:
    estimator = model.named_steps["model"]
    preprocess = model.named_steps["preprocess"]
    try:
        cat_names = preprocess.named_transformers_["cat"].named_steps["encoder"].get_feature_names_out(categorical)
        names = list(numeric) + list(cat_names)
        values = estimator.feature_importances_
        return pd.DataFrame({"feature": names, "importance": values}).sort_values("importance", ascending=False).head(25)
    except Exception:
        return pd.DataFrame(columns=["feature", "importance"])


def _baseline_appeal_scores(denials: pd.DataFrame) -> pd.DataFrame:
    scored = denials[
        [
            "denial_key",
            "claim_id",
            "issuer_name",
            "plan_name",
            "service_line",
            "denial_reason_category",
            "denied_amount",
            "recoverable_amount",
            "expected_recovery_probability",
            "expected_recovery_value",
            "priority_score",
        ]
    ].copy()
    scored["appeal_success_probability"] = scored["expected_recovery_probability"].fillna(0.25).round(4)
    scored["model_expected_recovery_value"] = (scored["recoverable_amount"] * scored["appeal_success_probability"]).round(2)
    scored["priority_rank"] = scored["model_expected_recovery_value"].rank(ascending=False, method="first").astype(int)
    return scored.sort_values("priority_rank")
