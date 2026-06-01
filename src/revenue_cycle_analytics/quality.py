from __future__ import annotations

import math

import numpy as np
import pandas as pd


def run_quality_checks(
    tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    model_metrics: dict[str, object],
) -> pd.DataFrame:
    checks: list[dict[str, str]] = []

    benchmark = tables["fact_denial_benchmark"]
    claims = tables["fact_claim"]
    denials = tables["fact_denial"]
    appeals = tables["fact_appeal"]
    leakage = tables["fact_revenue_leakage"]
    work_queue = marts["mart_denial_work_queue"]
    underpayment = marts["mart_underpayment_opportunity"]

    _add(checks, "benchmark_claims_denied_not_above_received", (benchmark["claims_denied"] <= benchmark["claims_received"]).all(), "CMS-style benchmark rows are internally consistent.")
    _add(checks, "benchmark_denial_rate_between_zero_and_one", benchmark["denial_rate"].between(0, 1).all(), "Benchmark denial rates stay in valid probability range.")
    _add(checks, "benchmark_appeals_not_above_denials", (benchmark["appeals_filed"] <= benchmark["claims_denied"]).all(), "Benchmark appeal counts do not exceed denied claims.")
    _add(checks, "every_claim_has_plan_and_issuer", claims["plan_key"].notna().all() and claims["issuer_key"].notna().all(), "All simulated claims have plan and issuer keys.")
    _add(checks, "every_denial_has_reason", denials["denial_reason_key"].notna().all(), "Every denied claim maps to a denial reason.")
    _add(checks, "appeals_map_to_denials", set(appeals["denial_key"]).issubset(set(denials["denial_key"])), "Appeal records all map to known denials.")
    _add(checks, "paid_plus_denied_not_above_submitted", ((claims["paid_amount"] + claims["denied_amount"]) <= (claims["submitted_amount"] + 0.01)).all(), "Paid plus denied amount does not exceed submitted amount.")
    _add(checks, "revenue_leakage_non_negative", (leakage[["underpaid_amount", "recoverable_amount", "expected_recovery_value", "writeoff_amount"]] >= -0.01).all().all(), "Revenue leakage fields are non-negative.")
    _add(checks, "work_queue_has_actions", not work_queue.empty and work_queue["recommended_action"].notna().all(), "Open denials have recommended actions.")
    _add(checks, "work_queue_has_priority_scores", not work_queue.empty and work_queue["priority_score"].notna().all(), "Open denials have priority scores.")
    _add(checks, "underpayment_non_negative", underpayment.empty or (underpayment["underpaid_amount"] >= -0.01).all(), "Underpayment mart does not contain negative opportunities.")

    calibration = _calibration_error(claims, benchmark)
    _add(
        checks,
        "simulation_calibration_within_tolerance",
        calibration["max_abs_error"] <= 0.08,
        f"Max plan-level denial-rate calibration error is {calibration['max_abs_error']:.3f}; target tolerance is 0.080.",
        warn_only=calibration["max_abs_error"] <= 0.10,
    )
    _add(
        checks,
        "model_metrics_available",
        _metrics_are_reasonable(model_metrics),
        "Model metrics were produced and probability metrics are finite when applicable.",
    )

    output = pd.DataFrame(checks)
    status_order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    return output.sort_values("status", key=lambda s: s.map(status_order)).reset_index(drop=True)


def _add(checks: list[dict[str, str]], name: str, condition: bool, detail: str, warn_only: bool = False) -> None:
    if condition:
        status = "PASS"
    elif warn_only:
        status = "WARN"
    else:
        status = "FAIL"
    checks.append({"check_name": name, "status": status, "detail": detail})


def _calibration_error(claims: pd.DataFrame, benchmark: pd.DataFrame) -> dict[str, float]:
    actual = claims.groupby("plan_key")["denied_flag"].mean()
    target = benchmark.set_index("plan_key")["denial_rate"]
    comparison = pd.concat([actual.rename("actual"), target.rename("target")], axis=1).dropna()
    comparison["abs_error"] = (comparison["actual"] - comparison["target"]).abs()
    return {
        "mean_abs_error": float(comparison["abs_error"].mean()),
        "max_abs_error": float(comparison["abs_error"].max()),
    }


def _metrics_are_reasonable(model_metrics: dict[str, object]) -> bool:
    if not model_metrics:
        return False
    for metrics in model_metrics.values():
        if not isinstance(metrics, dict):
            return False
        if "rows_trained" not in metrics or int(metrics["rows_trained"]) <= 0:
            return False
        for key in ["roc_auc", "average_precision", "precision_at_top_decile", "recall_at_top_decile"]:
            value = metrics.get(key)
            if value is None:
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                return False
            if key in {"roc_auc", "average_precision", "precision_at_top_decile", "recall_at_top_decile"} and not 0 <= float(value) <= 1:
                return False
    return True

