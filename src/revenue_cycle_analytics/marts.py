from __future__ import annotations

import numpy as np
import pandas as pd


def build_marts(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    claim = tables["fact_claim"]
    denial = tables["fact_denial"]
    appeal = tables["fact_appeal"]
    leakage = tables["fact_revenue_leakage"]
    issuer = tables["dim_issuer"]
    plan = tables["dim_plan"]
    service = tables["dim_service"]
    reason = tables["dim_denial_reason"]
    provider = tables["dim_provider"]
    contract = tables["fact_contract_rate"]

    enriched = (
        claim.merge(issuer[["issuer_key", "issuer_name", "state_code"]], on="issuer_key", how="left")
        .merge(plan[["plan_key", "plan_name", "metal_level", "network_type"]], on="plan_key", how="left")
        .merge(service[["service_key", "service_type"]], on="service_key", how="left")
    )
    denial_enriched = (
        denial.merge(reason[["denial_reason_key", "denial_reason_category"]], on="denial_reason_key", how="left")
        .merge(claim[["claim_key", "claim_id", "issuer_key", "plan_key", "provider_key", "service_key", "claim_received_date_key", "expected_payment_amount", "paid_amount", "network_status"]], on="claim_key", how="left")
        .merge(issuer[["issuer_key", "issuer_name", "state_code"]], on="issuer_key", how="left")
        .merge(plan[["plan_key", "plan_name", "metal_level", "network_type"]], on="plan_key", how="left")
        .merge(provider[["provider_key", "provider_name", "provider_type"]], on="provider_key", how="left")
        .merge(service[["service_key", "service_line", "service_type"]], on="service_key", how="left")
        .merge(leakage, on=["claim_key", "denial_key"], how="left", suffixes=("", "_leakage"))
    )

    denial_rate = _denial_rate_mart(enriched, denial_enriched)
    appeal_performance = _appeal_performance_mart(denial_enriched, appeal)
    revenue_leakage = _revenue_leakage_mart(denial_enriched)
    denial_work_queue = _work_queue_mart(denial_enriched)
    payer_scorecard = _payer_scorecard_mart(enriched, denial_enriched, appeal, leakage)
    service_line_denials = _service_line_denials_mart(enriched, denial_enriched)
    underpayment = _underpayment_opportunity_mart(enriched, provider, contract, issuer, plan, service)

    return {
        "mart_denial_rate": denial_rate,
        "mart_appeal_performance": appeal_performance,
        "mart_revenue_leakage": revenue_leakage,
        "mart_denial_work_queue": denial_work_queue,
        "mart_payer_scorecard": payer_scorecard,
        "mart_service_line_denials": service_line_denials,
        "mart_underpayment_opportunity": underpayment,
    }


def _denial_rate_mart(claim: pd.DataFrame, denial: pd.DataFrame) -> pd.DataFrame:
    received = (
        claim.groupby(["issuer_name", "plan_name", "state_code", "service_line", "network_status"], dropna=False)
        .agg(claims_received=("claim_key", "nunique"), submitted_amount=("submitted_amount", "sum"), expected_payment_amount=("expected_payment_amount", "sum"))
        .reset_index()
    )
    denied = (
        denial.groupby(["issuer_name", "plan_name", "state_code", "service_line", "network_status"], dropna=False)
        .agg(denied_claims=("denial_key", "nunique"), denied_amount=("denied_amount", "sum"), preventable_denials=("preventable_flag", "sum"))
        .reset_index()
    )
    mart = received.merge(denied, on=["issuer_name", "plan_name", "state_code", "service_line", "network_status"], how="left")
    mart[["denied_claims", "denied_amount", "preventable_denials"]] = mart[["denied_claims", "denied_amount", "preventable_denials"]].fillna(0)
    mart["denial_rate"] = mart["denied_claims"] / mart["claims_received"]
    mart["preventable_denial_rate"] = np.where(mart["denied_claims"] > 0, mart["preventable_denials"] / mart["denied_claims"], 0)
    return mart.sort_values(["denial_rate", "denied_amount"], ascending=False)


def _appeal_performance_mart(denial: pd.DataFrame, appeal: pd.DataFrame) -> pd.DataFrame:
    if appeal.empty:
        return pd.DataFrame(columns=["issuer_name", "denial_reason_category", "denials", "appeals_filed", "appeal_rate", "appeal_success_rate", "recovered_amount"])
    appeal_enriched = appeal.merge(denial[["denial_key", "issuer_name", "plan_name", "service_line", "denial_reason_category", "denied_amount"]], on="denial_key", how="left")
    denials = denial.groupby(["issuer_name", "denial_reason_category"], dropna=False).agg(denials=("denial_key", "nunique"), denied_amount=("denied_amount", "sum")).reset_index()
    appeals = (
        appeal_enriched.groupby(["issuer_name", "denial_reason_category"], dropna=False)
        .agg(
            appeals_filed=("appeal_key", "nunique"),
            successful_appeals=("appeal_success_flag", "sum"),
            appealed_amount=("appealed_amount", "sum"),
            recovered_amount=("recovered_amount", "sum"),
            avg_days_to_decision=("days_to_decision", "mean"),
        )
        .reset_index()
    )
    mart = denials.merge(appeals, on=["issuer_name", "denial_reason_category"], how="left")
    numeric_cols = [
        "denials",
        "denied_amount",
        "appeals_filed",
        "successful_appeals",
        "appealed_amount",
        "recovered_amount",
        "avg_days_to_decision",
    ]
    for col in numeric_cols:
        mart[col] = pd.to_numeric(mart[col], errors="coerce").fillna(0)
    mart["appeal_rate"] = np.where(mart["denials"] > 0, mart["appeals_filed"] / mart["denials"], 0)
    mart["appeal_success_rate"] = np.where(mart["appeals_filed"] > 0, mart["successful_appeals"] / mart["appeals_filed"], 0)
    mart["recovery_rate"] = np.where(mart["appealed_amount"] > 0, mart["recovered_amount"] / mart["appealed_amount"], 0)
    return mart.sort_values(["recovered_amount", "appeal_success_rate"], ascending=False)


def _revenue_leakage_mart(denial: pd.DataFrame) -> pd.DataFrame:
    mart = (
        denial.groupby(["issuer_name", "plan_name", "service_line", "denial_reason_category"], dropna=False)
        .agg(
            denied_claims=("denial_key", "nunique"),
            denied_amount=("denied_amount", "sum"),
            recoverable_amount=("recoverable_amount", "sum"),
            expected_recovery_value=("expected_recovery_value", "sum"),
            actual_recovered_amount=("actual_recovered_amount", "sum"),
            avg_priority_score=("priority_score", "mean"),
        )
        .reset_index()
    )
    mart["unrecovered_opportunity"] = (mart["expected_recovery_value"] - mart["actual_recovered_amount"]).clip(lower=0)
    return mart.sort_values("expected_recovery_value", ascending=False)


def _work_queue_mart(denial: pd.DataFrame) -> pd.DataFrame:
    open_statuses = ["Open", "Appealable", "Pending appeal", "Pending review"]
    queue = denial[denial["denial_status"].isin(open_statuses)].copy()
    if queue.empty:
        return pd.DataFrame(columns=["claim_id", "issuer_name", "plan_name", "provider_name", "service_line", "denial_reason_category", "denied_amount", "recoverable_amount", "expected_recovery_probability", "expected_recovery_value", "days_since_denial", "priority_score", "recommended_action", "priority_tier"])
    today_key = int(queue["denial_date_key"].max())
    queue["days_since_denial"] = (
        pd.to_datetime(str(today_key)) - pd.to_datetime(queue["denial_date_key"].astype(str), errors="coerce")
    ).dt.days.clip(lower=0)
    queue["recommended_action"] = queue["denial_reason_category"].map(_recommended_action).fillna("Analyst review")
    queue["priority_tier"] = pd.qcut(queue["priority_score"].rank(method="first"), 4, labels=["Low", "Medium", "High", "Critical"])
    fields = [
        "claim_id",
        "issuer_name",
        "plan_name",
        "provider_name",
        "service_line",
        "denial_reason_category",
        "denied_amount",
        "recoverable_amount",
        "expected_recovery_probability",
        "expected_recovery_value",
        "days_since_denial",
        "priority_score",
        "recommended_action",
        "priority_tier",
    ]
    return queue[fields].sort_values("priority_score", ascending=False)


def _recommended_action(reason: str) -> str:
    return {
        "Missing documentation": "Submit documentation packet",
        "Prior authorization missing": "Validate authorization and appeal if supported",
        "Coding error": "Correct and resubmit",
        "Medical necessity": "Clinical appeal review",
        "Eligibility or coverage terminated": "Eligibility verification",
        "Timely filing": "Late filing exception review",
        "Out-of-network service": "Contracting or network exception review",
        "Duplicate claim": "Validate duplicate logic",
        "Bundling or modifier issue": "Coding modifier review",
    }.get(reason, "Analyst review")


def _payer_scorecard_mart(claim: pd.DataFrame, denial: pd.DataFrame, appeal: pd.DataFrame, leakage: pd.DataFrame) -> pd.DataFrame:
    claims = claim.groupby(["issuer_key", "issuer_name"], dropna=False).agg(claims_received=("claim_key", "nunique"), expected_payment_amount=("expected_payment_amount", "sum")).reset_index()
    denials = denial.groupby(["issuer_key", "issuer_name"], dropna=False).agg(denied_claims=("denial_key", "nunique"), denied_amount=("denied_amount", "sum"), doc_denials=("denial_reason_category", lambda s: (s == "Missing documentation").sum()), avg_days_to_denial=("days_to_denial", "mean")).reset_index()
    if appeal.empty:
        appeals = pd.DataFrame(columns=["issuer_key", "appeals_filed", "appeals_upheld", "avg_days_to_decision", "recovered_amount"])
    else:
        appeal_enriched = appeal.merge(denial[["denial_key", "issuer_key"]], on="denial_key", how="left")
        appeals = appeal_enriched.groupby("issuer_key").agg(
            appeals_filed=("appeal_key", "nunique"),
            appeals_upheld=("appeal_outcome", lambda s: (s == "Appeal upheld").sum()),
            avg_days_to_decision=("days_to_decision", "mean"),
            recovered_amount=("recovered_amount", "sum"),
        ).reset_index()
    underpaid = leakage.merge(denial[["denial_key", "issuer_key"]], on="denial_key", how="left").groupby("issuer_key").agg(underpaid_amount=("underpaid_amount", "sum"), expected_recovery_value=("expected_recovery_value", "sum")).reset_index()
    mart = claims.merge(denials, on=["issuer_key", "issuer_name"], how="left").merge(appeals, on="issuer_key", how="left").merge(underpaid, on="issuer_key", how="left")
    numeric_cols = [
        "denied_claims",
        "denied_amount",
        "doc_denials",
        "avg_days_to_denial",
        "appeals_filed",
        "appeals_upheld",
        "avg_days_to_decision",
        "recovered_amount",
        "underpaid_amount",
        "expected_recovery_value",
    ]
    for col in numeric_cols:
        mart[col] = pd.to_numeric(mart[col], errors="coerce").fillna(0)
    mart["denial_rate"] = mart["denied_claims"] / mart["claims_received"]
    mart["appeal_upheld_rate"] = np.where(mart["appeals_filed"] > 0, mart["appeals_upheld"] / mart["appeals_filed"], 0)
    mart["underpayment_rate"] = np.where(mart["expected_payment_amount"] > 0, mart["underpaid_amount"] / mart["expected_payment_amount"], 0)
    mart["documentation_denial_share"] = np.where(mart["denied_claims"] > 0, mart["doc_denials"] / mart["denied_claims"], 0)
    mart["payer_friction_score"] = (
        0.35 * mart["denial_rate"].rank(pct=True)
        + 0.20 * mart["appeal_upheld_rate"].rank(pct=True)
        + 0.20 * mart["avg_days_to_decision"].rank(pct=True)
        + 0.15 * mart["underpayment_rate"].rank(pct=True)
        + 0.10 * mart["documentation_denial_share"].rank(pct=True)
    )
    mart["friction_tier"] = pd.cut(
        mart["payer_friction_score"],
        bins=[0, 0.45, 0.68, 0.84, 1.01],
        labels=["Low friction", "Moderate friction", "High friction", "Contracting review required"],
        include_lowest=True,
    )
    return mart.sort_values("payer_friction_score", ascending=False)


def _service_line_denials_mart(claim: pd.DataFrame, denial: pd.DataFrame) -> pd.DataFrame:
    received = claim.groupby("service_line").agg(claims_received=("claim_key", "nunique"), expected_payment_amount=("expected_payment_amount", "sum")).reset_index()
    denied = denial.groupby("service_line").agg(
        denied_claims=("denial_key", "nunique"),
        denied_amount=("denied_amount", "sum"),
        preventable_denials=("preventable_flag", "sum"),
        expected_recovery_value=("expected_recovery_value", "sum"),
    ).reset_index()
    mart = received.merge(denied, on="service_line", how="left").fillna(0)
    mart["denial_rate"] = mart["denied_claims"] / mart["claims_received"]
    mart["preventable_share"] = np.where(mart["denied_claims"] > 0, mart["preventable_denials"] / mart["denied_claims"], 0)
    return mart.sort_values("expected_recovery_value", ascending=False)


def _underpayment_opportunity_mart(
    claim: pd.DataFrame,
    provider: pd.DataFrame,
    contract: pd.DataFrame,
    issuer: pd.DataFrame,
    plan: pd.DataFrame,
    service: pd.DataFrame,
) -> pd.DataFrame:
    paid_claims = claim[claim["claim_status"].isin(["Paid", "Partially denied"])].copy()
    matched = paid_claims.merge(
        contract[["provider_key", "issuer_key", "plan_key", "service_key", "payer_negotiated_rate", "rate_confidence_score"]],
        on=["provider_key", "issuer_key", "plan_key", "service_key"],
        how="left",
    )
    matched["contract_rate_amount"] = matched["payer_negotiated_rate"].fillna(matched["expected_payment_amount"])
    matched["underpaid_amount"] = (matched["contract_rate_amount"] - matched["paid_amount"]).clip(lower=0)
    matched["underpayment_flag"] = matched["underpaid_amount"] > 25
    matched["contract_review_flag"] = matched["underpayment_flag"] & (matched["rate_confidence_score"].fillna(0.55) >= 0.70)
    output = matched.merge(provider[["provider_key", "provider_name"]], on="provider_key", how="left")
    fields = [
        "claim_id",
        "provider_name",
        "issuer_name",
        "plan_name",
        "service_line",
        "expected_payment_amount",
        "paid_amount",
        "contract_rate_amount",
        "underpaid_amount",
        "underpayment_flag",
        "contract_review_flag",
        "rate_confidence_score",
    ]
    return output[fields].sort_values("underpaid_amount", ascending=False)
