from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data_generation import DENIAL_REASONS, GeneratedData


DEFAULT_PLAN_YEAR = 2025


ALIASES = {
    "claim_id": ["claim_id", "claim_number", "claim", "claim_no", "claimid"],
    "member_id": ["member_id", "patient_id", "member", "patient"],
    "issuer_name": ["issuer_name", "payer", "payer_name", "insurer", "insurance_company", "carrier"],
    "plan_name": ["plan_name", "plan", "insurance_plan"],
    "state_code": ["state_code", "state", "market_state"],
    "provider_name": ["provider_name", "provider", "facility", "facility_name", "billing_provider"],
    "provider_type": ["provider_type", "facility_type"],
    "service_line": ["service_line", "service", "department", "specialty", "service_category"],
    "claim_status": ["claim_status", "status", "adjudication_status"],
    "denial_reason_category": ["denial_reason_category", "denial_reason", "denial_category", "reason", "denial_code"],
    "denial_status": ["denial_status"],
    "network_status": ["network_status", "network", "in_network"],
    "submitted_amount": ["submitted_amount", "billed_amount", "charge_amount", "charges", "claim_amount"],
    "allowed_amount": ["allowed_amount", "allowed"],
    "expected_payment_amount": ["expected_payment_amount", "expected_payment", "expected_reimbursement", "contract_amount"],
    "paid_amount": ["paid_amount", "paid", "payment_amount", "reimbursed_amount"],
    "denied_amount": ["denied_amount", "denied"],
    "member_responsibility_amount": ["member_responsibility_amount", "member_responsibility", "patient_responsibility"],
    "claim_received_date": ["claim_received_date", "received_date", "submitted_date", "claim_date"],
    "service_from_date": ["service_from_date", "service_date", "date_of_service"],
    "service_thru_date": ["service_thru_date", "service_to_date"],
    "adjudication_date": ["adjudication_date", "processed_date", "decision_date"],
    "appeal_outcome": ["appeal_outcome", "appeal_result"],
    "appeal_status": ["appeal_status"],
    "appealed_amount": ["appealed_amount"],
    "recovered_amount": ["recovered_amount", "appeal_recovered_amount"],
    "prior_auth_required_flag": ["prior_auth_required_flag", "prior_auth_required", "auth_required"],
    "prior_auth_present_flag": ["prior_auth_present_flag", "prior_auth_present", "auth_present"],
    "documentation_required_flag": ["documentation_required_flag", "documentation_required", "docs_required"],
    "documentation_present_flag": ["documentation_present_flag", "documentation_present", "docs_present"],
    "timely_filing_flag": ["timely_filing_flag", "timely_filing"],
    "duplicate_claim_flag": ["duplicate_claim_flag", "duplicate_claim"],
    "risk_segment": ["risk_segment", "member_risk_segment"],
    "coverage_status": ["coverage_status", "member_coverage_status"],
}


SERVICE_DEFAULTS = {
    "Inpatient": ("IP", "Institutional", 1.40, 17_500),
    "Outpatient surgery": ("OPS", "Institutional", 1.20, 7_800),
    "Emergency department": ("ED", "Institutional", 1.00, 2_600),
    "Imaging": ("IMG", "Professional", 1.10, 1_450),
    "Lab": ("LAB", "Professional", 0.65, 240),
    "Durable medical equipment": ("DME", "Professional", 1.35, 950),
    "Professional E/M": ("EM", "Professional", 0.75, 210),
    "Behavioral health": ("BH", "Professional", 1.25, 320),
    "Pharmacy": ("RX", "Professional", 0.80, 180),
    "Therapy": ("THER", "Professional", 1.15, 380),
}


def load_custom_claims_dataset(csv_path: Path, plan_year: int = DEFAULT_PLAN_YEAR) -> GeneratedData:
    source = pd.read_csv(csv_path)
    if source.empty:
        raise ValueError(f"Custom claims file is empty: {csv_path}")

    frame = _canonicalize_columns(source)
    frame = _normalize_claim_frame(frame, plan_year)

    dim_issuer = _make_issuers(frame)
    dim_plan = _make_plans(frame, dim_issuer, plan_year)
    dim_member = _make_members(frame, dim_plan)
    dim_provider = _make_providers(frame)
    dim_service = _make_services(frame)
    dim_denial_reason = _make_denial_reasons(frame)
    dim_date = _make_date_dimension(frame, plan_year)

    fact_claim = _make_claims(frame, dim_issuer, dim_plan, dim_member, dim_provider, dim_service, dim_denial_reason)
    fact_denial = _make_denials(fact_claim, dim_denial_reason)
    fact_appeal = _make_appeals(frame, fact_claim, fact_denial)
    fact_revenue_leakage = _make_revenue_leakage(fact_claim, fact_denial, fact_appeal, dim_denial_reason)
    fact_contract_rate = _make_contract_rates(fact_claim)
    fact_denial_benchmark = _make_benchmarks(fact_claim, fact_denial, fact_appeal, plan_year)

    return GeneratedData(
        dim_date=dim_date,
        dim_issuer=dim_issuer,
        dim_plan=dim_plan,
        dim_member_simulated=dim_member,
        dim_provider=dim_provider,
        dim_service=dim_service,
        dim_denial_reason=dim_denial_reason,
        fact_denial_benchmark=fact_denial_benchmark,
        fact_claim=fact_claim,
        fact_denial=fact_denial,
        fact_appeal=fact_appeal,
        fact_contract_rate=fact_contract_rate,
        fact_revenue_leakage=fact_revenue_leakage,
    )


def _canonicalize_columns(source: pd.DataFrame) -> pd.DataFrame:
    cleaned = source.copy()
    cleaned.columns = [_clean_name(column) for column in cleaned.columns]
    output = pd.DataFrame(index=cleaned.index)
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if _clean_name(alias) in cleaned.columns:
                output[canonical] = cleaned[_clean_name(alias)]
                break
    for column in cleaned.columns:
        if column not in output.columns:
            output[column] = cleaned[column]
    return output


def _clean_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace("/", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("__", "_")
    )


def _normalize_claim_frame(frame: pd.DataFrame, plan_year: int) -> pd.DataFrame:
    output = frame.copy()
    row_count = len(output)
    output["claim_id"] = _text(output.get("claim_id"), [f"CUSTOM-CLM-{i + 1:07d}" for i in range(row_count)])
    output["member_id"] = _text(output.get("member_id"), [f"CUSTOM-MBR-{(i % max(1, row_count // 3)) + 1:07d}" for i in range(row_count)])
    output["issuer_name"] = _text(output.get("issuer_name"), "Custom Payer", row_count)
    output["plan_name"] = _text(output.get("plan_name"), output["issuer_name"].astype(str) + " Standard Plan")
    output["state_code"] = _text(output.get("state_code"), "XX", row_count).str.upper().str.slice(0, 2)
    output["provider_name"] = _text(output.get("provider_name"), "Custom Provider", row_count)
    output["provider_type"] = _text(output.get("provider_type"), "Professional Group", row_count)
    output["service_line"] = _text(output.get("service_line"), "Professional E/M", row_count).map(_normalize_service_line)
    output["network_status"] = _text(output.get("network_status"), "In-network", row_count).map(_normalize_network_status)
    output["submitted_amount"] = _amount(output.get("submitted_amount"), 1000.0, row_count)
    output["allowed_amount"] = _amount(output.get("allowed_amount"), output["submitted_amount"] * 0.58)
    output["expected_payment_amount"] = _amount(output.get("expected_payment_amount"), output["allowed_amount"] * 0.86)

    raw_status = _text(output.get("claim_status"), "", row_count)
    raw_reason = _text(output.get("denial_reason_category"), "", row_count)
    raw_paid = output.get("paid_amount")
    output["paid_amount"] = _amount(raw_paid, np.nan, row_count)
    inferred_denied = raw_status.str.contains("den|partial|reject", case=False, na=False) | raw_reason.str.strip().ne("")
    paid_fallback = pd.Series(np.where(inferred_denied, 0.0, output["expected_payment_amount"]), index=output.index)
    output["paid_amount"] = output["paid_amount"].fillna(paid_fallback)
    output["denied_amount"] = _amount(output.get("denied_amount"), np.nan, row_count)
    output["denied_amount"] = output["denied_amount"].fillna((output["expected_payment_amount"] - output["paid_amount"]).clip(lower=0))
    output["denied_flag"] = inferred_denied
    output.loc[~output["denied_flag"], "denied_amount"] = 0.0
    output["claim_status"] = raw_status.where(raw_status.str.strip().ne(""), np.where(output["denied_flag"], "Denied", "Paid"))
    output["denial_reason_category"] = raw_reason.map(_normalize_denial_reason)
    output.loc[output["denied_flag"] & output["denial_reason_category"].eq(""), "denial_reason_category"] = "Coding error"
    output["member_responsibility_amount"] = _amount(output.get("member_responsibility_amount"), (output["allowed_amount"] - output["expected_payment_amount"]).clip(lower=0))

    output["claim_received_date"] = _date(output.get("claim_received_date"), plan_year, length=row_count)
    output["service_from_date"] = _date(output.get("service_from_date"), plan_year, fallback=output["claim_received_date"] - pd.to_timedelta(7, unit="D"), length=row_count)
    output["service_thru_date"] = _date(output.get("service_thru_date"), plan_year, fallback=output["service_from_date"], length=row_count)
    output["adjudication_date"] = _date(output.get("adjudication_date"), plan_year, fallback=output["claim_received_date"] + pd.to_timedelta(14, unit="D"), length=row_count)

    output["prior_auth_required_flag"] = _bool(output.get("prior_auth_required_flag"), output["service_line"].isin(["Inpatient", "Outpatient surgery", "Imaging", "Therapy"]))
    output["prior_auth_present_flag"] = _bool(output.get("prior_auth_present_flag"), True, row_count)
    output["documentation_required_flag"] = _bool(output.get("documentation_required_flag"), output["service_line"].isin(["Inpatient", "Outpatient surgery", "Therapy", "Durable medical equipment"]))
    output["documentation_present_flag"] = _bool(output.get("documentation_present_flag"), True, row_count)
    output["timely_filing_flag"] = _bool(output.get("timely_filing_flag"), True, row_count)
    output["duplicate_claim_flag"] = _bool(output.get("duplicate_claim_flag"), False, row_count)
    output["risk_segment"] = _text(output.get("risk_segment"), "Moderate", row_count)
    output["coverage_status"] = _text(output.get("coverage_status"), "Active", row_count)
    output["denial_status"] = _text(output.get("denial_status"), pd.Series(np.where(output["denied_flag"], "Appealable", "Closed"), index=output.index))
    output["appeal_outcome"] = _text(output.get("appeal_outcome"), "", row_count)
    output["appeal_status"] = _text(output.get("appeal_status"), "", row_count)
    output["appealed_amount"] = _amount(output.get("appealed_amount"), output["denied_amount"])
    output["recovered_amount"] = _amount(output.get("recovered_amount"), np.nan)
    output["source_year"] = plan_year
    return output


def _text(values: object, default: object, length: int | None = None) -> pd.Series:
    if values is None:
        values = default
    if isinstance(values, pd.Series):
        series = values.copy()
    else:
        series = pd.Series(values)
    if len(series) == 1 and length and length > 1:
        series = pd.Series([series.iloc[0]] * length)
    series = series.astype("object")
    if isinstance(default, pd.Series):
        fallback = default.astype("object")
    elif isinstance(default, list):
        fallback = pd.Series(default, index=series.index)
    else:
        fallback = pd.Series([default] * (length or len(series)), index=series.index if len(series) == (length or len(series)) else None)
    if length and len(series) != length:
        series = pd.Series([series.iloc[0] if len(series) else ""] * length)
        fallback = fallback.reset_index(drop=True).reindex(range(length)).ffill().bfill()
    return series.where(series.notna() & series.astype(str).str.strip().ne(""), fallback).astype(str).str.strip()


def _amount(values: object, default: object, length: int | None = None) -> pd.Series:
    if values is None:
        if isinstance(default, pd.Series):
            return pd.to_numeric(default, errors="coerce").fillna(0.0).round(2)
        return pd.Series(default if isinstance(default, (list, np.ndarray)) else [default] * (length or 1)).astype(float)
    series = pd.to_numeric(pd.Series(values).replace(r"[\$,]", "", regex=True), errors="coerce")
    if isinstance(default, pd.Series):
        fallback = pd.to_numeric(default, errors="coerce")
    elif isinstance(default, (list, np.ndarray)):
        fallback = pd.Series(default, index=series.index)
    else:
        fallback = pd.Series([default] * len(series), index=series.index)
    return series.fillna(fallback).fillna(0.0).round(2)


def _bool(values: object, default: object, length: int | None = None) -> pd.Series:
    if values is None:
        if isinstance(default, pd.Series):
            return default.astype(bool)
        return pd.Series([bool(default)] * (length or 1))
    series = pd.Series(values)
    mapped = series.astype(str).str.strip().str.lower().map(
        {
            "true": True,
            "t": True,
            "yes": True,
            "y": True,
            "1": True,
            "in-network": True,
            "false": False,
            "f": False,
            "no": False,
            "n": False,
            "0": False,
            "out-of-network": False,
        }
    )
    if isinstance(default, pd.Series):
        fallback = default.astype(bool)
    else:
        fallback = pd.Series([bool(default)] * len(series), index=series.index)
    return mapped.fillna(fallback).astype(bool)


def _date(values: object, plan_year: int, fallback: object | None = None, length: int | None = None) -> pd.Series:
    if values is None:
        if fallback is not None:
            return pd.to_datetime(fallback)
        start = pd.Timestamp(plan_year, 1, 1)
        return pd.Series([start + pd.Timedelta(days=int(i % 365)) for i in range(length or 1)])
    parsed = pd.to_datetime(values, errors="coerce")
    if fallback is None:
        fallback_series = pd.Series([pd.Timestamp(plan_year, 1, 1) + pd.Timedelta(days=int(i % 365)) for i in range(len(parsed))], index=parsed.index)
    else:
        fallback_series = pd.to_datetime(fallback)
    return pd.Series(parsed, index=parsed.index).fillna(fallback_series)


def _date_key(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values).dt.strftime("%Y%m%d").astype(int)


def _normalize_network_status(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"false", "no", "0", "out", "oon", "out-of-network", "out of network"}:
        return "Out-of-network"
    return "In-network"


def _normalize_service_line(value: object) -> str:
    text = str(value).strip()
    lookup = {key.lower(): key for key in SERVICE_DEFAULTS}
    return lookup.get(text.lower(), text.title() if text else "Professional E/M")


def _normalize_denial_reason(value: object) -> str:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "not appealed"}:
        return ""
    by_code = {code.lower(): category for code, category, *_ in DENIAL_REASONS}
    by_category = {category.lower(): category for _, category, *_ in DENIAL_REASONS}
    return by_code.get(text.lower(), by_category.get(text.lower(), text.title()))


def _make_issuers(frame: pd.DataFrame) -> pd.DataFrame:
    rows = frame[["issuer_name", "state_code"]].drop_duplicates().reset_index(drop=True)
    rows.insert(0, "issuer_key", range(1, len(rows) + 1))
    rows["issuer_id"] = rows["issuer_key"].map(lambda value: f"CUST-ISS-{value:04d}")
    rows["market_type"] = "Custom"
    rows["source_year"] = frame["source_year"].iloc[0]
    return rows[["issuer_key", "issuer_id", "issuer_name", "state_code", "market_type", "source_year"]]


def _make_plans(frame: pd.DataFrame, issuers: pd.DataFrame, plan_year: int) -> pd.DataFrame:
    rows = frame[["issuer_name", "plan_name", "state_code"]].drop_duplicates().merge(issuers[["issuer_key", "issuer_name"]], on="issuer_name")
    rows = rows.reset_index(drop=True)
    rows.insert(0, "plan_key", range(1, len(rows) + 1))
    rows["plan_id"] = rows["plan_key"].map(lambda value: f"CUST-PLAN-{value:04d}")
    rows["plan_year"] = plan_year
    rows["metal_level"] = "Custom"
    rows["market_type"] = "Custom"
    rows["network_type"] = "Custom"
    rows["service_area_id"] = rows["state_code"].map(lambda value: f"CUST-{value}")
    rows["qhp_flag"] = False
    rows["allowed_ratio"] = 0.58
    return rows[
        [
            "plan_key",
            "plan_id",
            "issuer_key",
            "plan_year",
            "plan_name",
            "metal_level",
            "market_type",
            "network_type",
            "state_code",
            "service_area_id",
            "qhp_flag",
            "allowed_ratio",
        ]
    ]


def _make_members(frame: pd.DataFrame, plans: pd.DataFrame) -> pd.DataFrame:
    rows = frame[["member_id", "plan_name", "state_code", "risk_segment", "coverage_status"]].drop_duplicates()
    rows = rows.merge(plans[["plan_key", "plan_name"]], on="plan_name", how="left").reset_index(drop=True)
    rows.insert(0, "member_key", range(1, len(rows) + 1))
    rows["age_band"] = "Unknown"
    rows["sex"] = "Unknown"
    return rows[["member_key", "member_id", "age_band", "sex", "state_code", "risk_segment", "coverage_status", "plan_key"]]


def _make_providers(frame: pd.DataFrame) -> pd.DataFrame:
    rows = frame[["provider_name", "provider_type", "state_code", "network_status"]].drop_duplicates().reset_index(drop=True)
    rows.insert(0, "provider_key", range(1, len(rows) + 1))
    rows["npi"] = rows["provider_key"].map(lambda value: f"CUSTNPI{value:07d}")
    rows["specialty_group"] = rows["provider_type"]
    rows["taxonomy_code"] = "CUSTOM"
    return rows[["provider_key", "npi", "provider_name", "provider_type", "specialty_group", "state_code", "taxonomy_code", "network_status"]]


def _make_services(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for service_key, service_line in enumerate(sorted(frame["service_line"].dropna().unique()), start=1):
        code, service_type, risk, base_charge = SERVICE_DEFAULTS.get(service_line, (f"CUST{service_key:03d}", "Professional", 1.0, float(frame["submitted_amount"].median())))
        rows.append(
            {
                "service_key": service_key,
                "service_code": code,
                "service_description": service_line,
                "service_type": service_type,
                "service_line": service_line,
                "revenue_center": f"CUST-RC-{service_key:03d}",
                "requires_prior_auth_flag": service_line in {"Inpatient", "Outpatient surgery", "Imaging", "Therapy"},
                "high_documentation_risk_flag": service_line in {"Inpatient", "Outpatient surgery", "Therapy", "Durable medical equipment"},
                "medical_necessity_review_flag": risk >= 1.1,
                "risk_weight": risk,
                "prior_auth_rate": 0.35,
                "documentation_rate": 0.40,
                "base_charge": base_charge,
            }
        )
    return pd.DataFrame(rows)


def _make_denial_reasons(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, row in enumerate(DENIAL_REASONS, start=1):
        code, category, preventable, front_end, appealable, root_cause, owner = row
        rows.append(
            {
                "denial_reason_key": key,
                "denial_reason_code": code,
                "denial_reason_category": category,
                "denial_reason_description": category,
                "preventable_flag": preventable,
                "front_end_edit_flag": front_end,
                "appealable_flag": appealable,
                "root_cause": root_cause,
                "typical_owner": owner,
            }
        )
    known = {row["denial_reason_category"] for row in rows}
    for category in sorted(set(frame.loc[frame["denied_flag"], "denial_reason_category"]) - known - {""}):
        rows.append(
            {
                "denial_reason_key": len(rows) + 1,
                "denial_reason_code": f"CUST{len(rows) + 1:03d}",
                "denial_reason_category": category,
                "denial_reason_description": category,
                "preventable_flag": False,
                "front_end_edit_flag": False,
                "appealable_flag": True,
                "root_cause": "Custom source reason",
                "typical_owner": "Analyst review",
            }
        )
    return pd.DataFrame(rows)


def _make_date_dimension(frame: pd.DataFrame, plan_year: int) -> pd.DataFrame:
    date_values = pd.concat(
        [
            frame["claim_received_date"],
            frame["service_from_date"],
            frame["service_thru_date"],
            frame["adjudication_date"],
        ],
        ignore_index=True,
    )
    start = min(pd.Timestamp(plan_year, 1, 1), pd.to_datetime(date_values).min())
    end = max(pd.Timestamp(plan_year, 12, 31), pd.to_datetime(date_values).max())
    dates = pd.date_range(start.normalize(), end.normalize(), freq="D")
    return pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "full_date": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "quarter": dates.quarter,
            "month": dates.month,
            "month_name": dates.strftime("%b"),
            "week_of_year": dates.isocalendar().week.astype(int).to_numpy(),
            "day_of_week": dates.day_name(),
        }
    )


def _make_claims(
    frame: pd.DataFrame,
    issuers: pd.DataFrame,
    plans: pd.DataFrame,
    members: pd.DataFrame,
    providers: pd.DataFrame,
    services: pd.DataFrame,
    reasons: pd.DataFrame,
) -> pd.DataFrame:
    claims = frame.reset_index(drop=True).copy()
    claims.insert(0, "claim_key", range(1, len(claims) + 1))
    claims = claims.merge(issuers[["issuer_key", "issuer_name"]], on="issuer_name", how="left")
    claims = claims.merge(plans[["plan_key", "plan_name"]], on="plan_name", how="left")
    claims = claims.merge(members[["member_key", "member_id", "plan_key"]], on=["member_id", "plan_key"], how="left")
    claims = claims.merge(providers[["provider_key", "provider_name", "provider_type", "network_status"]], on=["provider_name", "provider_type", "network_status"], how="left")
    claims = claims.merge(services[["service_key", "service_line", "service_type", "risk_weight"]], on="service_line", how="left")
    claims = claims.merge(reasons[["denial_reason_key", "denial_reason_category"]], on="denial_reason_category", how="left")
    claims["denial_reason_key"] = claims["denial_reason_key"].fillna(0).astype(int).replace(0, pd.NA)
    plan_rates = claims.groupby("plan_key")["denied_flag"].mean().rename("benchmark_denial_rate")
    claims = claims.merge(plan_rates, on="plan_key", how="left")
    claims["claim_received_date_key"] = _date_key(claims["claim_received_date"])
    claims["service_from_date_key"] = _date_key(claims["service_from_date"])
    claims["service_thru_date_key"] = _date_key(claims["service_thru_date"])
    claims["adjudication_date_key"] = _date_key(claims["adjudication_date"])
    claims["claim_type"] = np.where(claims["service_type"].eq("Institutional"), "Institutional", "Professional")
    claims["simulated_flag"] = False
    claims["member_coverage_status"] = claims["coverage_status"]
    claims["member_risk_segment"] = claims["risk_segment"]
    claims["service_risk_weight"] = claims["risk_weight"].fillna(1.0)
    claims["paid_amount"] = claims[["paid_amount", "expected_payment_amount"]].min(axis=1).round(2)
    claims["denied_amount"] = claims["denied_amount"].round(2)
    return claims[
        [
            "claim_key",
            "claim_id",
            "member_key",
            "plan_key",
            "issuer_key",
            "provider_key",
            "service_key",
            "claim_received_date_key",
            "service_from_date_key",
            "service_thru_date_key",
            "adjudication_date_key",
            "claim_type",
            "claim_status",
            "submitted_amount",
            "allowed_amount",
            "expected_payment_amount",
            "paid_amount",
            "member_responsibility_amount",
            "network_status",
            "prior_auth_required_flag",
            "prior_auth_present_flag",
            "documentation_required_flag",
            "documentation_present_flag",
            "timely_filing_flag",
            "duplicate_claim_flag",
            "simulated_flag",
            "benchmark_denial_rate",
            "member_coverage_status",
            "member_risk_segment",
            "service_line",
            "service_risk_weight",
            "denied_flag",
            "denial_reason_category",
            "denial_reason_key",
            "denied_amount",
        ]
    ]


def _make_denials(claims: pd.DataFrame, reasons: pd.DataFrame) -> pd.DataFrame:
    denied = claims[claims["denied_flag"]].copy()
    reason_lookup = reasons.set_index("denial_reason_key")
    rows = []
    for denial_key, claim in enumerate(denied.itertuples(index=False), start=1):
        reason = reason_lookup.loc[int(claim.denial_reason_key)]
        days_to_denial = max(1, int((pd.to_datetime(str(claim.adjudication_date_key)) - pd.to_datetime(str(claim.claim_received_date_key))).days))
        rows.append(
            {
                "denial_key": denial_key,
                "claim_key": int(claim.claim_key),
                "denial_reason_key": int(claim.denial_reason_key),
                "denial_date_key": int(claim.adjudication_date_key),
                "denied_amount": round(float(claim.denied_amount), 2),
                "preventable_flag": bool(reason["preventable_flag"]),
                "appealable_flag": bool(reason["appealable_flag"]),
                "denial_owner": reason["typical_owner"],
                "root_cause": reason["root_cause"],
                "days_to_denial": days_to_denial,
                "denial_status": "Appealable" if bool(reason["appealable_flag"]) else "Open",
            }
        )
    return pd.DataFrame(rows)


def _make_appeals(frame: pd.DataFrame, claims: pd.DataFrame, denials: pd.DataFrame) -> pd.DataFrame:
    if denials.empty:
        return pd.DataFrame(columns=_APPEAL_COLUMNS)
    appeal_source = frame.reset_index(drop=True).copy()
    appeal_source["claim_key"] = range(1, len(appeal_source) + 1)
    appeal_source = appeal_source.merge(denials[["denial_key", "claim_key", "denied_amount"]], on="claim_key", how="inner")
    appeal_source = appeal_source[appeal_source["appeal_outcome"].str.strip().ne("")]
    rows = []
    for appeal in appeal_source.itertuples(index=False):
        outcome = str(appeal.appeal_outcome)
        if outcome.lower() in {"not appealed", "none", "nan"}:
            continue
        success = "overturn" in outcome.lower() or "success" in outcome.lower() or "partial" in outcome.lower()
        recovered = appeal.recovered_amount
        if pd.isna(recovered):
            recovered = float(appeal.denied_amount) * (0.85 if "overturn" in outcome.lower() else 0.45 if "partial" in outcome.lower() else 0.0)
        appeal_date = pd.to_datetime(appeal.adjudication_date) + pd.Timedelta(days=7)
        decision_date = appeal_date + pd.Timedelta(days=24)
        rows.append(
            {
                "appeal_key": len(rows) + 1,
                "denial_key": int(appeal.denial_key),
                "appeal_created_date_key": int(appeal_date.strftime("%Y%m%d")),
                "appeal_submitted_date_key": int(appeal_date.strftime("%Y%m%d")),
                "appeal_decision_date_key": int(decision_date.strftime("%Y%m%d")),
                "appeal_level": "First level",
                "appeal_status": appeal.appeal_status if str(appeal.appeal_status).strip() else "Closed",
                "appeal_outcome": outcome,
                "appealed_amount": round(float(appeal.appealed_amount), 2),
                "recovered_amount": round(float(recovered), 2),
                "days_to_appeal": 7,
                "days_to_decision": 24,
                "appeal_success_flag": bool(success),
            }
        )
    return pd.DataFrame(rows, columns=_APPEAL_COLUMNS)


_APPEAL_COLUMNS = [
    "appeal_key",
    "denial_key",
    "appeal_created_date_key",
    "appeal_submitted_date_key",
    "appeal_decision_date_key",
    "appeal_level",
    "appeal_status",
    "appeal_outcome",
    "appealed_amount",
    "recovered_amount",
    "days_to_appeal",
    "days_to_decision",
    "appeal_success_flag",
]


def _make_revenue_leakage(claims: pd.DataFrame, denials: pd.DataFrame, appeals: pd.DataFrame, reasons: pd.DataFrame) -> pd.DataFrame:
    if denials.empty:
        return pd.DataFrame(columns=["claim_key", "denial_key", "submitted_amount", "expected_payment_amount", "paid_amount", "denied_amount", "underpaid_amount", "recoverable_amount", "writeoff_amount", "expected_recovery_probability", "expected_recovery_value", "priority_score", "actual_recovered_amount", "appeal_success_flag"])
    claim_lookup = claims.set_index("claim_key")
    reason_lookup = reasons.set_index("denial_reason_key")
    appeal_recovery = appeals.groupby("denial_key")["recovered_amount"].sum() if not appeals.empty else pd.Series(dtype=float)
    appeal_success = appeals.groupby("denial_key")["appeal_success_flag"].max() if not appeals.empty else pd.Series(dtype=bool)
    rows = []
    for denial in denials.itertuples(index=False):
        claim = claim_lookup.loc[int(denial.claim_key)]
        reason = reason_lookup.loc[int(denial.denial_reason_key)]
        probability = _recovery_probability(reason["denial_reason_category"], bool(reason["preventable_flag"]))
        recoverable = float(denial.denied_amount) * (0.86 if bool(reason["appealable_flag"]) else 0.18)
        recovered = float(appeal_recovery.get(int(denial.denial_key), 0.0))
        expected_value = recoverable * probability
        underpaid = max(float(claim["expected_payment_amount"]) - float(claim["paid_amount"]) - float(denial.denied_amount), 0.0)
        rows.append(
            {
                "claim_key": int(denial.claim_key),
                "denial_key": int(denial.denial_key),
                "submitted_amount": float(claim["submitted_amount"]),
                "expected_payment_amount": float(claim["expected_payment_amount"]),
                "paid_amount": float(claim["paid_amount"]),
                "denied_amount": float(denial.denied_amount),
                "underpaid_amount": round(underpaid, 2),
                "recoverable_amount": round(recoverable, 2),
                "writeoff_amount": round(max(float(denial.denied_amount) - recoverable - recovered, 0.0), 2),
                "expected_recovery_probability": round(probability, 4),
                "expected_recovery_value": round(expected_value, 2),
                "priority_score": round(0.42 * expected_value + 0.22 * probability * 1000 + 0.16 * (100 if bool(reason["preventable_flag"]) else 20) + 0.12 * (100 if bool(reason["appealable_flag"]) else 15), 2),
                "actual_recovered_amount": round(recovered, 2),
                "appeal_success_flag": bool(appeal_success.get(int(denial.denial_key), False)),
            }
        )
    return pd.DataFrame(rows)


def _recovery_probability(reason: str, preventable: bool) -> float:
    base = {
        "Missing documentation": 0.58,
        "Coding error": 0.54,
        "Prior authorization missing": 0.42,
        "Medical necessity": 0.34,
        "Eligibility or coverage terminated": 0.28,
        "Timely filing": 0.24,
        "Out-of-network service": 0.22,
        "Duplicate claim": 0.18,
    }.get(reason, 0.33)
    return min(0.72, base + (0.04 if preventable else 0.0))


def _make_contract_rates(claims: pd.DataFrame) -> pd.DataFrame:
    groups = claims.groupby(["provider_key", "issuer_key", "plan_key", "service_key"], as_index=False).agg(
        expected_payment_amount=("expected_payment_amount", "median"),
        submitted_amount=("submitted_amount", "median"),
    )
    rows = []
    for key, row in enumerate(groups.itertuples(index=False), start=1):
        negotiated = max(float(row.expected_payment_amount) * 1.04, 1.0)
        gross = max(float(row.submitted_amount), negotiated * 1.35)
        rows.append(
            {
                "contract_rate_key": key,
                "provider_key": int(row.provider_key),
                "issuer_key": int(row.issuer_key),
                "plan_key": int(row.plan_key),
                "service_key": int(row.service_key),
                "rate_effective_date": f"{DEFAULT_PLAN_YEAR}-01-01",
                "gross_charge": round(gross, 2),
                "discounted_cash_price": round(gross * 0.62, 2),
                "payer_negotiated_rate": round(negotiated, 2),
                "deidentified_min_rate": round(negotiated * 0.82, 2),
                "deidentified_max_rate": round(negotiated * 1.28, 2),
                "rate_source_file": "custom_claims_derived_contract_rates.csv",
                "rate_confidence_score": 0.72,
            }
        )
    return pd.DataFrame(rows)


def _make_benchmarks(claims: pd.DataFrame, denials: pd.DataFrame, appeals: pd.DataFrame, plan_year: int) -> pd.DataFrame:
    claim_counts = claims.groupby(["issuer_key", "plan_key"], as_index=False).agg(claims_received=("claim_key", "nunique"))
    denial_counts = denials.merge(claims[["claim_key", "issuer_key", "plan_key"]], on="claim_key", how="left").groupby(["issuer_key", "plan_key"], as_index=False).agg(claims_denied=("denial_key", "nunique"))
    if appeals.empty:
        appeal_counts = pd.DataFrame(columns=["issuer_key", "plan_key", "appeals_filed", "appeals_upheld", "appeals_overturned"])
    else:
        appeal_counts = (
            appeals.merge(denials[["denial_key", "claim_key"]], on="denial_key", how="left")
            .merge(claims[["claim_key", "issuer_key", "plan_key"]], on="claim_key", how="left")
            .groupby(["issuer_key", "plan_key"], as_index=False)
            .agg(
                appeals_filed=("appeal_key", "nunique"),
                appeals_upheld=("appeal_outcome", lambda values: values.astype(str).str.contains("upheld", case=False, na=False).sum()),
                appeals_overturned=("appeal_success_flag", "sum"),
            )
        )
    rows = claim_counts.merge(denial_counts, on=["issuer_key", "plan_key"], how="left").merge(appeal_counts, on=["issuer_key", "plan_key"], how="left").fillna(0)
    rows["plan_year"] = plan_year
    rows["network_status"] = "All"
    rows["denial_rate"] = rows["claims_denied"] / rows["claims_received"]
    rows["appeal_rate"] = np.where(rows["claims_denied"] > 0, rows["appeals_filed"] / rows["claims_denied"], 0)
    rows["appeal_upheld_rate"] = np.where(rows["appeals_filed"] > 0, rows["appeals_upheld"] / rows["appeals_filed"], 0)
    rows["appeal_overturn_rate"] = np.where(rows["appeals_filed"] > 0, rows["appeals_overturned"] / rows["appeals_filed"], 0)
    return rows[["issuer_key", "plan_key", "plan_year", "network_status", "claims_received", "claims_denied", "appeals_filed", "appeals_upheld", "appeals_overturned", "denial_rate", "appeal_rate", "appeal_upheld_rate", "appeal_overturn_rate"]]
