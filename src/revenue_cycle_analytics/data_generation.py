from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


DENIAL_REASONS = [
    ("ELIG", "Eligibility or coverage terminated", True, True, True, "Eligibility", "Registration"),
    ("AUTH", "Prior authorization missing", True, True, True, "Authorization", "Authorization"),
    ("MEDNEC", "Medical necessity", False, False, True, "Medical necessity", "Clinical documentation"),
    ("CODING", "Coding error", True, True, True, "Coding", "Coding"),
    ("DOC", "Missing documentation", True, True, True, "Documentation", "Clinical documentation"),
    ("DUP", "Duplicate claim", True, True, False, "Duplicate submission", "Billing"),
    ("TIMELY", "Timely filing", True, True, True, "Late submission", "Billing"),
    ("COB", "Coordination of benefits", True, True, True, "COB", "Billing"),
    ("NONCOV", "Non-covered service", False, False, True, "Coverage policy", "Payer policy"),
    ("OON", "Out-of-network service", False, False, True, "Network status", "Contracting"),
    ("BENMAX", "Benefit maximum exceeded", False, False, True, "Benefit limit", "Payer policy"),
    ("NPI", "Invalid provider identifier", True, True, True, "Provider master data", "Registration"),
    ("BUNDLE", "Bundling or modifier issue", True, True, True, "Modifier logic", "Coding"),
    ("EXPER", "Experimental/investigational", False, False, True, "Medical policy", "Payer policy"),
    ("REFERRAL", "Referral missing", True, True, True, "Referral", "Authorization"),
]

SERVICE_LINES = [
    ("IP", "Inpatient", 1.4, 0.55, 0.82, 17_500),
    ("OPS", "Outpatient surgery", 1.2, 0.68, 0.76, 7_800),
    ("ED", "Emergency department", 1.0, 0.12, 0.38, 2_600),
    ("IMG", "Imaging", 1.1, 0.48, 0.48, 1_450),
    ("LAB", "Lab", 0.65, 0.08, 0.28, 240),
    ("DME", "Durable medical equipment", 1.35, 0.42, 0.62, 950),
    ("EM", "Professional E/M", 0.75, 0.08, 0.22, 210),
    ("BH", "Behavioral health", 1.25, 0.30, 0.55, 320),
    ("RX", "Pharmacy", 0.8, 0.16, 0.20, 180),
    ("THER", "Therapy", 1.15, 0.36, 0.60, 380),
]

STATE_CODES = ["CA", "TX", "FL", "NY", "IL", "GA", "PA", "NC", "AZ", "OH"]
METAL_LEVELS = ["Bronze", "Silver", "Gold", "Platinum"]
NETWORK_TYPES = ["HMO", "PPO", "EPO", "POS"]
ISSUER_NAMES = [
    "Apex Health",
    "BrightPath Insurance",
    "CareBridge Plans",
    "Evergreen Mutual",
    "HarborWell Health",
    "Northstar Assurance",
    "PrairieCare",
    "Summit Choice",
]
PROVIDER_TYPES = ["Hospital", "Ambulatory Surgery Center", "Professional Group", "Imaging Center", "Lab", "DME Supplier"]
RISK_SEGMENTS = ["Low", "Moderate", "High", "Complex"]


@dataclass(frozen=True)
class GeneratedData:
    dim_date: pd.DataFrame
    dim_issuer: pd.DataFrame
    dim_plan: pd.DataFrame
    dim_member_simulated: pd.DataFrame
    dim_provider: pd.DataFrame
    dim_service: pd.DataFrame
    dim_denial_reason: pd.DataFrame
    fact_denial_benchmark: pd.DataFrame
    fact_claim: pd.DataFrame
    fact_denial: pd.DataFrame
    fact_appeal: pd.DataFrame
    fact_contract_rate: pd.DataFrame
    fact_revenue_leakage: pd.DataFrame

    def as_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "dim_date": self.dim_date,
            "dim_issuer": self.dim_issuer,
            "dim_plan": self.dim_plan,
            "dim_member_simulated": self.dim_member_simulated,
            "dim_provider": self.dim_provider,
            "dim_service": self.dim_service,
            "dim_denial_reason": self.dim_denial_reason,
            "fact_denial_benchmark": self.fact_denial_benchmark,
            "fact_claim": self.fact_claim,
            "fact_denial": self.fact_denial,
            "fact_appeal": self.fact_appeal,
            "fact_contract_rate": self.fact_contract_rate,
            "fact_revenue_leakage": self.fact_revenue_leakage,
        }


def generate_dataset(
    seed: int = 42,
    claim_count: int = 12_000,
    member_count: int = 4_500,
    provider_count: int = 180,
    plan_year: int = 2025,
) -> GeneratedData:
    rng = np.random.default_rng(seed)
    dim_date = _make_date_dimension(plan_year)
    dim_issuer = _make_issuers()
    dim_plan = _make_plans(rng, dim_issuer, plan_year)
    dim_member = _make_members(rng, member_count, dim_plan)
    dim_provider = _make_providers(rng, provider_count)
    dim_service = _make_services()
    dim_denial_reason = _make_denial_reasons()
    benchmark = _make_benchmarks(rng, dim_issuer, dim_plan, plan_year)
    contract_rate = _make_contract_rates(rng, dim_provider, dim_issuer, dim_plan, dim_service)

    fact_claim = _make_claims(
        rng,
        claim_count,
        dim_date,
        dim_member,
        dim_plan,
        dim_issuer,
        dim_provider,
        dim_service,
        benchmark,
    )
    fact_claim = _simulate_denials(rng, fact_claim, dim_service, dim_denial_reason, benchmark)
    fact_denial = _make_denials(fact_claim, dim_denial_reason)
    fact_appeal = _make_appeals(rng, fact_denial, fact_claim, dim_denial_reason, dim_date)
    fact_revenue_leakage = _make_revenue_leakage(fact_claim, fact_denial, fact_appeal, dim_denial_reason)
    fact_claim, fact_denial = _apply_denial_statuses(fact_claim, fact_denial, fact_appeal)

    return GeneratedData(
        dim_date=dim_date,
        dim_issuer=dim_issuer,
        dim_plan=dim_plan,
        dim_member_simulated=dim_member,
        dim_provider=dim_provider,
        dim_service=dim_service,
        dim_denial_reason=dim_denial_reason,
        fact_denial_benchmark=benchmark,
        fact_claim=fact_claim,
        fact_denial=fact_denial,
        fact_appeal=fact_appeal,
        fact_contract_rate=contract_rate,
        fact_revenue_leakage=fact_revenue_leakage,
    )


def _date_key(values: pd.Series | pd.DatetimeIndex) -> pd.Series:
    parsed = pd.to_datetime(values)
    if isinstance(parsed, pd.Series):
        return parsed.dt.strftime("%Y%m%d").astype(int)
    return pd.Series(parsed.strftime("%Y%m%d").astype(int))


def _make_date_dimension(plan_year: int) -> pd.DataFrame:
    dates = pd.date_range(date(plan_year, 1, 1), date(plan_year, 12, 31), freq="D")
    return pd.DataFrame(
        {
            "date_key": _date_key(dates).to_numpy(),
            "full_date": dates.strftime("%Y-%m-%d").to_numpy(),
            "year": dates.year.to_numpy(),
            "quarter": dates.quarter.to_numpy(),
            "month": dates.month.to_numpy(),
            "month_name": dates.strftime("%b").to_numpy(),
            "week_of_year": dates.isocalendar().week.astype(int).to_numpy(),
            "day_of_week": dates.day_name().to_numpy(),
        }
    )


def _make_issuers() -> pd.DataFrame:
    rows = []
    for issuer_key, name in enumerate(ISSUER_NAMES, start=1):
        rows.append(
            {
                "issuer_key": issuer_key,
                "issuer_id": f"ISS{issuer_key:04d}",
                "issuer_name": name,
                "state_code": STATE_CODES[(issuer_key - 1) % len(STATE_CODES)],
                "market_type": "Individual",
                "source_year": 2025,
            }
        )
    return pd.DataFrame(rows)


def _make_plans(rng: np.random.Generator, issuers: pd.DataFrame, plan_year: int) -> pd.DataFrame:
    rows = []
    plan_key = 1
    for issuer in issuers.to_dict("records"):
        for plan_idx in range(1, 4):
            metal = METAL_LEVELS[(issuer["issuer_key"] + plan_idx) % len(METAL_LEVELS)]
            network = NETWORK_TYPES[(issuer["issuer_key"] + plan_idx * 2) % len(NETWORK_TYPES)]
            rows.append(
                {
                    "plan_key": plan_key,
                    "plan_id": f"{issuer['issuer_id']}-{plan_idx}",
                    "issuer_key": issuer["issuer_key"],
                    "plan_year": plan_year,
                    "plan_name": f"{issuer['issuer_name']} {metal} {network}",
                    "metal_level": metal,
                    "market_type": issuer["market_type"],
                    "network_type": network,
                    "state_code": issuer["state_code"],
                    "service_area_id": f"SA-{issuer['state_code']}-{plan_idx}",
                    "qhp_flag": True,
                    "allowed_ratio": float(rng.uniform(0.42, 0.74)),
                }
            )
            plan_key += 1
    return pd.DataFrame(rows)


def _make_members(rng: np.random.Generator, member_count: int, plans: pd.DataFrame) -> pd.DataFrame:
    plan_keys = rng.choice(plans["plan_key"], size=member_count)
    plan_state = plans.set_index("plan_key")["state_code"]
    coverage = rng.choice(["Active", "Inactive", "Grace period"], size=member_count, p=[0.965, 0.018, 0.017])
    rows = []
    for idx in range(member_count):
        plan_key = int(plan_keys[idx])
        rows.append(
            {
                "member_key": idx + 1,
                "member_id": f"MBR{idx + 1:07d}",
                "age_band": rng.choice(["0-17", "18-34", "35-49", "50-64", "65+"], p=[0.11, 0.24, 0.27, 0.28, 0.10]),
                "sex": rng.choice(["F", "M"], p=[0.52, 0.48]),
                "state_code": plan_state.loc[plan_key],
                "risk_segment": rng.choice(RISK_SEGMENTS, p=[0.42, 0.34, 0.18, 0.06]),
                "coverage_status": coverage[idx],
                "plan_key": plan_key,
            }
        )
    return pd.DataFrame(rows)


def _make_providers(rng: np.random.Generator, provider_count: int) -> pd.DataFrame:
    specialty_by_type = {
        "Hospital": ["Acute care", "Community hospital", "Children's hospital"],
        "Ambulatory Surgery Center": ["Surgery", "Orthopedics", "Gastroenterology"],
        "Professional Group": ["Primary care", "Cardiology", "Behavioral health", "Physical medicine"],
        "Imaging Center": ["Radiology", "Advanced imaging"],
        "Lab": ["Clinical laboratory", "Pathology"],
        "DME Supplier": ["Durable medical equipment", "Home health equipment"],
    }
    rows = []
    for key in range(1, provider_count + 1):
        provider_type = rng.choice(PROVIDER_TYPES, p=[0.18, 0.12, 0.42, 0.10, 0.10, 0.08])
        rows.append(
            {
                "provider_key": key,
                "npi": f"{rng.integers(10_000_0000, 99_999_9999)}",
                "provider_name": f"{rng.choice(['Metro', 'Lakeside', 'Valley', 'Summit', 'Harbor', 'North'])} {provider_type} {key:03d}",
                "provider_type": provider_type,
                "specialty_group": rng.choice(specialty_by_type[provider_type]),
                "state_code": rng.choice(STATE_CODES),
                "taxonomy_code": f"{rng.integers(1000000000, 9999999999)}X",
                "network_status": rng.choice(["In-network", "Out-of-network"], p=[0.82, 0.18]),
            }
        )
    return pd.DataFrame(rows)


def _make_services() -> pd.DataFrame:
    rows = []
    for service_key, (code, line, risk, auth_rate, doc_rate, base_charge) in enumerate(SERVICE_LINES, start=1):
        rows.append(
            {
                "service_key": service_key,
                "service_code": code,
                "service_description": line,
                "service_type": "Institutional" if line in {"Inpatient", "Outpatient surgery", "Emergency department"} else "Professional",
                "service_line": line,
                "revenue_center": f"RC-{service_key:03d}",
                "requires_prior_auth_flag": auth_rate >= 0.30,
                "high_documentation_risk_flag": doc_rate >= 0.48,
                "medical_necessity_review_flag": risk >= 1.10,
                "risk_weight": risk,
                "prior_auth_rate": auth_rate,
                "documentation_rate": doc_rate,
                "base_charge": base_charge,
            }
        )
    return pd.DataFrame(rows)


def _make_denial_reasons() -> pd.DataFrame:
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
    return pd.DataFrame(rows)


def _make_benchmarks(
    rng: np.random.Generator,
    issuers: pd.DataFrame,
    plans: pd.DataFrame,
    plan_year: int,
) -> pd.DataFrame:
    issuer_base = {
        int(row.issuer_key): float(rng.uniform(0.11, 0.22))
        for row in issuers.itertuples(index=False)
    }
    rows = []
    for plan in plans.to_dict("records"):
        target = float(np.clip(issuer_base[plan["issuer_key"]] + rng.normal(0, 0.018), 0.09, 0.285))
        received = int(rng.integers(18_000, 95_000))
        denied = int(round(received * target))
        appeal_rate = float(np.clip(rng.normal(0.23, 0.07), 0.08, 0.46))
        appeals = int(round(denied * appeal_rate))
        overturn_rate = float(np.clip(0.42 - target + rng.normal(0, 0.06), 0.11, 0.56))
        overturned = int(round(appeals * overturn_rate))
        upheld = max(0, appeals - overturned - int(round(appeals * float(rng.uniform(0.04, 0.09)))))
        rows.append(
            {
                "issuer_key": plan["issuer_key"],
                "plan_key": plan["plan_key"],
                "plan_year": plan_year,
                "network_status": "All",
                "claims_received": received,
                "claims_denied": denied,
                "appeals_filed": appeals,
                "appeals_upheld": upheld,
                "appeals_overturned": overturned,
                "denial_rate": denied / received,
                "appeal_rate": appeals / denied if denied else 0.0,
                "appeal_upheld_rate": upheld / appeals if appeals else 0.0,
                "appeal_overturn_rate": overturned / appeals if appeals else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _make_contract_rates(
    rng: np.random.Generator,
    providers: pd.DataFrame,
    issuers: pd.DataFrame,
    plans: pd.DataFrame,
    services: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    key = 1
    hospital_candidates = providers[providers["provider_type"].isin(["Hospital", "Ambulatory Surgery Center", "Imaging Center"])]
    if hospital_candidates.empty:
        hospital_candidates = providers
    hospital_like = hospital_candidates.sample(n=min(45, len(hospital_candidates)), random_state=7)
    for provider in hospital_like.to_dict("records"):
        selected_plans = plans.sample(n=min(6, len(plans)), random_state=provider["provider_key"])
        for plan in selected_plans.to_dict("records"):
            issuer = issuers.loc[issuers["issuer_key"] == plan["issuer_key"]].iloc[0]
            for service in services.sample(n=5, random_state=provider["provider_key"] + plan["plan_key"]).to_dict("records"):
                gross = service["base_charge"] * float(rng.uniform(1.8, 4.6))
                negotiated = gross * float(rng.uniform(0.24, 0.58))
                rows.append(
                    {
                        "contract_rate_key": key,
                        "provider_key": provider["provider_key"],
                        "issuer_key": int(issuer["issuer_key"]),
                        "plan_key": int(plan["plan_key"]),
                        "service_key": int(service["service_key"]),
                        "rate_effective_date": "2025-01-01",
                        "gross_charge": round(gross, 2),
                        "discounted_cash_price": round(gross * float(rng.uniform(0.35, 0.72)), 2),
                        "payer_negotiated_rate": round(negotiated, 2),
                        "deidentified_min_rate": round(negotiated * float(rng.uniform(0.72, 0.90)), 2),
                        "deidentified_max_rate": round(negotiated * float(rng.uniform(1.12, 1.45)), 2),
                        "rate_source_file": "simulated_hospital_price_transparency_sample.csv",
                        "rate_confidence_score": round(float(rng.uniform(0.70, 0.96)), 3),
                    }
                )
                key += 1
    return pd.DataFrame(rows)


def _make_claims(
    rng: np.random.Generator,
    claim_count: int,
    dim_date: pd.DataFrame,
    members: pd.DataFrame,
    plans: pd.DataFrame,
    issuers: pd.DataFrame,
    providers: pd.DataFrame,
    services: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> pd.DataFrame:
    plan_lookup = plans.set_index("plan_key")
    member_sample = members.sample(n=claim_count, replace=True, random_state=11).reset_index(drop=True)
    provider_keys = rng.choice(providers["provider_key"], size=claim_count)
    service_probs = np.array([0.055, 0.08, 0.12, 0.12, 0.22, 0.055, 0.22, 0.055, 0.045, 0.05])
    service_probs = service_probs / service_probs.sum()
    service_keys = rng.choice(services["service_key"], size=claim_count, p=service_probs)
    service_lookup = services.set_index("service_key")
    provider_lookup = providers.set_index("provider_key")
    benchmark_lookup = benchmark.set_index("plan_key")["denial_rate"]
    received_offsets = rng.integers(0, len(dim_date), size=claim_count)
    received_dates = pd.to_datetime(dim_date.iloc[received_offsets]["full_date"].to_numpy())
    service_from_dates = received_dates - pd.to_timedelta(rng.integers(1, 32, size=claim_count), unit="D")
    service_thru_dates = service_from_dates + pd.to_timedelta(rng.integers(0, 4, size=claim_count), unit="D")
    adjudication_dates = received_dates + pd.to_timedelta(rng.integers(4, 38, size=claim_count), unit="D")

    rows = []
    for idx in range(claim_count):
        member = member_sample.iloc[idx]
        plan = plan_lookup.loc[int(member["plan_key"])]
        provider = provider_lookup.loc[int(provider_keys[idx])]
        service = service_lookup.loc[int(service_keys[idx])]
        submitted = float(rng.lognormal(mean=np.log(service["base_charge"]), sigma=0.45))
        submitted = max(60.0, min(submitted, service["base_charge"] * 6.5))
        allowed = submitted * float(plan["allowed_ratio"]) * float(rng.uniform(0.86, 1.12))
        member_resp = allowed * float(rng.uniform(0.04, 0.22))
        expected_payment = max(0.0, allowed - member_resp)
        prior_auth_required = bool(rng.random() < float(service["prior_auth_rate"]))
        documentation_required = bool(rng.random() < float(service["documentation_rate"]))
        network_status = (
            "Out-of-network"
            if provider["network_status"] == "Out-of-network" or rng.random() < (0.06 if plan["network_type"] != "PPO" else 0.025)
            else "In-network"
        )
        rows.append(
            {
                "claim_key": idx + 1,
                "claim_id": f"CLM{idx + 1:09d}",
                "member_key": int(member["member_key"]),
                "plan_key": int(member["plan_key"]),
                "issuer_key": int(plan["issuer_key"]),
                "provider_key": int(provider_keys[idx]),
                "service_key": int(service_keys[idx]),
                "claim_received_date_key": int(_date_key(pd.Series([received_dates[idx]])).iloc[0]),
                "service_from_date_key": int(_date_key(pd.Series([service_from_dates[idx]])).iloc[0]),
                "service_thru_date_key": int(_date_key(pd.Series([service_thru_dates[idx]])).iloc[0]),
                "adjudication_date_key": int(_date_key(pd.Series([adjudication_dates[idx]])).iloc[0]),
                "claim_type": "Institutional" if service["service_type"] == "Institutional" else "Professional",
                "claim_status": "Submitted",
                "submitted_amount": round(submitted, 2),
                "allowed_amount": round(allowed, 2),
                "expected_payment_amount": round(expected_payment, 2),
                "paid_amount": 0.0,
                "member_responsibility_amount": round(member_resp, 2),
                "network_status": network_status,
                "prior_auth_required_flag": prior_auth_required,
                "prior_auth_present_flag": bool(not prior_auth_required or rng.random() < (0.95 if network_status == "In-network" else 0.86)),
                "documentation_required_flag": documentation_required,
                "documentation_present_flag": bool(not documentation_required or rng.random() < 0.94),
                "timely_filing_flag": bool(rng.random() > 0.014),
                "duplicate_claim_flag": bool(rng.random() < 0.008),
                "simulated_flag": True,
                "benchmark_denial_rate": float(benchmark_lookup.loc[int(member["plan_key"])]),
                "member_coverage_status": member["coverage_status"],
                "member_risk_segment": member["risk_segment"],
                "service_line": service["service_line"],
                "service_risk_weight": float(service["risk_weight"]),
            }
        )
    return pd.DataFrame(rows)


def _simulate_denials(
    rng: np.random.Generator,
    claims: pd.DataFrame,
    services: pd.DataFrame,
    denial_reasons: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> pd.DataFrame:
    claims = claims.copy()
    reason_lookup = denial_reasons.set_index("denial_reason_category")["denial_reason_key"].to_dict()
    claims["denied_flag"] = False
    claims["denial_reason_category"] = pd.NA
    claims["denial_reason_key"] = pd.NA

    deterministic_rules = [
        (claims["member_coverage_status"].eq("Inactive"), "Eligibility or coverage terminated"),
        (claims["duplicate_claim_flag"], "Duplicate claim"),
        (~claims["timely_filing_flag"], "Timely filing"),
        (claims["prior_auth_required_flag"] & ~claims["prior_auth_present_flag"], "Prior authorization missing"),
        (claims["documentation_required_flag"] & ~claims["documentation_present_flag"], "Missing documentation"),
    ]
    for mask, reason in deterministic_rules:
        unassigned = mask & ~claims["denied_flag"]
        claims.loc[unassigned, "denied_flag"] = True
        claims.loc[unassigned, "denial_reason_category"] = reason
        claims.loc[unassigned, "denial_reason_key"] = reason_lookup[reason]

    base_risk = (
        claims["benchmark_denial_rate"]
        + (claims["network_status"].eq("Out-of-network").astype(float) * 0.035)
        + ((claims["service_risk_weight"] - 1.0) * 0.045)
        + (claims["member_risk_segment"].eq("Complex").astype(float) * 0.018)
        + (claims["submitted_amount"].rank(pct=True) * 0.025)
    ).clip(0.02, 0.60)
    claims["_risk_score"] = base_risk + rng.normal(0, 0.018, len(claims))

    target_rates = benchmark.set_index("plan_key")["denial_rate"]
    for plan_key, group in claims.groupby("plan_key"):
        target = int(round(len(group) * float(target_rates.loc[plan_key])))
        already = int(group["denied_flag"].sum())
        remaining = claims.loc[group.index[~group["denied_flag"]]]
        add_count = max(0, min(len(remaining), target - already))
        if add_count == 0:
            continue
        selected = remaining.sort_values("_risk_score", ascending=False).head(add_count).index
        claims.loc[selected, "denied_flag"] = True
        claims.loc[selected, "denial_reason_category"] = _assign_probabilistic_reasons(rng, claims.loc[selected])
        claims.loc[selected, "denial_reason_key"] = claims.loc[selected, "denial_reason_category"].map(reason_lookup)

    partial_denial = claims["denied_flag"] & (rng.random(len(claims)) < 0.22)
    full_denial = claims["denied_flag"] & ~partial_denial
    pended = ~claims["denied_flag"] & (rng.random(len(claims)) < 0.026)
    approved = ~claims["denied_flag"] & ~pended

    claims.loc[full_denial, "claim_status"] = "Denied"
    claims.loc[partial_denial, "claim_status"] = "Partially denied"
    claims.loc[pended, "claim_status"] = "Pended"
    claims.loc[approved, "claim_status"] = "Paid"

    underpayment_factor = np.where(rng.random(len(claims)) < 0.115, rng.uniform(0.74, 0.94, len(claims)), rng.uniform(0.97, 1.03, len(claims)))
    claims.loc[approved, "paid_amount"] = (claims.loc[approved, "expected_payment_amount"] * underpayment_factor[approved.to_numpy()]).round(2)
    claims.loc[pended, "paid_amount"] = 0.0
    claims.loc[full_denial, "paid_amount"] = 0.0
    claims.loc[partial_denial, "paid_amount"] = (
        claims.loc[partial_denial, "expected_payment_amount"] * rng.uniform(0.25, 0.72, partial_denial.sum())
    ).round(2)

    claims["denied_amount"] = np.where(
        claims["denied_flag"],
        (claims["expected_payment_amount"] - claims["paid_amount"]).clip(lower=0),
        0.0,
    ).round(2)
    claims["paid_amount"] = claims[["paid_amount", "expected_payment_amount"]].min(axis=1).round(2)
    return claims.drop(columns=["_risk_score"])


def _assign_probabilistic_reasons(rng: np.random.Generator, claims: pd.DataFrame) -> np.ndarray:
    reasons = []
    for row in claims.itertuples(index=False):
        candidates = ["Coding error", "Medical necessity", "Non-covered service", "Coordination of benefits", "Bundling or modifier issue"]
        weights = np.array([0.26, 0.24, 0.16, 0.13, 0.12], dtype=float)
        if row.network_status == "Out-of-network":
            candidates.append("Out-of-network service")
            weights = np.append(weights, 0.22)
        if row.service_line in {"Therapy", "DME", "Behavioral health"}:
            candidates.append("Benefit maximum exceeded")
            weights = np.append(weights, 0.12)
        if row.service_line in {"Imaging", "Outpatient surgery", "Inpatient"}:
            candidates.append("Referral missing")
            weights = np.append(weights, 0.09)
        weights = weights / weights.sum()
        reasons.append(rng.choice(candidates, p=weights))
    return np.array(reasons)


def _make_denials(claims: pd.DataFrame, denial_reasons: pd.DataFrame) -> pd.DataFrame:
    denied = claims[claims["denied_flag"]].copy()
    reason_lookup = denial_reasons.set_index("denial_reason_key")
    rows = []
    for denial_key, row in enumerate(denied.itertuples(index=False), start=1):
        reason = reason_lookup.loc[int(row.denial_reason_key)]
        days_to_denial = max(1, int((pd.to_datetime(str(row.adjudication_date_key)) - pd.to_datetime(str(row.claim_received_date_key))).days))
        rows.append(
            {
                "denial_key": denial_key,
                "claim_key": int(row.claim_key),
                "denial_reason_key": int(row.denial_reason_key),
                "denial_date_key": int(row.adjudication_date_key),
                "denied_amount": round(float(row.denied_amount), 2),
                "preventable_flag": bool(reason["preventable_flag"]),
                "appealable_flag": bool(reason["appealable_flag"]),
                "denial_owner": reason["typical_owner"],
                "root_cause": reason["root_cause"],
                "days_to_denial": days_to_denial,
                "denial_status": "Open",
            }
        )
    return pd.DataFrame(rows)


def _make_appeals(
    rng: np.random.Generator,
    denials: pd.DataFrame,
    claims: pd.DataFrame,
    denial_reasons: pd.DataFrame,
    dim_date: pd.DataFrame,
) -> pd.DataFrame:
    if denials.empty:
        return pd.DataFrame(
            columns=[
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
        )

    reason_lookup = denial_reasons.set_index("denial_reason_key")
    claim_lookup = claims.set_index("claim_key")
    rows = []
    last_date_key = int(dim_date["date_key"].max())
    for row in denials.itertuples(index=False):
        reason = reason_lookup.loc[int(row.denial_reason_key)]
        claim = claim_lookup.loc[int(row.claim_key)]
        amount_factor = min(0.20, float(row.denied_amount) / 50_000)
        base_prob = 0.18 + amount_factor + (0.10 if bool(reason["appealable_flag"]) else -0.12)
        base_prob += 0.07 if bool(reason["preventable_flag"]) else 0.0
        base_prob += 0.06 if claim["service_line"] in {"Inpatient", "Outpatient surgery", "Imaging"} else 0.0
        if rng.random() > float(np.clip(base_prob, 0.04, 0.62)):
            continue

        days_to_appeal = int(rng.integers(3, 31))
        days_to_decision = int(rng.integers(12, 74))
        created_date = pd.to_datetime(str(row.denial_date_key)) + pd.Timedelta(days=int(rng.integers(1, 5)))
        submitted_date = pd.to_datetime(str(row.denial_date_key)) + pd.Timedelta(days=days_to_appeal)
        decision_date = submitted_date + pd.Timedelta(days=days_to_decision)
        if int(decision_date.strftime("%Y%m%d")) > last_date_key:
            decision_date_key = pd.NA
            status = "Pending"
            outcome = "Appealed pending"
            recovered = 0.0
            success = False
        else:
            success_prob = _appeal_success_probability(reason["denial_reason_category"], bool(reason["preventable_flag"]))
            roll = rng.random()
            if roll < success_prob * 0.65:
                outcome = "Appeal overturned"
                recovered = float(row.denied_amount) * float(rng.uniform(0.72, 0.98))
                success = True
            elif roll < success_prob:
                outcome = "Appeal partially overturned"
                recovered = float(row.denied_amount) * float(rng.uniform(0.30, 0.68))
                success = True
            elif roll < success_prob + 0.08:
                outcome = "Appeal dismissed"
                recovered = 0.0
                success = False
            else:
                outcome = "Appeal upheld"
                recovered = 0.0
                success = False
            status = "Closed"
            decision_date_key = int(decision_date.strftime("%Y%m%d"))

        rows.append(
            {
                "appeal_key": len(rows) + 1,
                "denial_key": int(row.denial_key),
                "appeal_created_date_key": int(created_date.strftime("%Y%m%d")),
                "appeal_submitted_date_key": int(submitted_date.strftime("%Y%m%d")),
                "appeal_decision_date_key": decision_date_key,
                "appeal_level": rng.choice(["First level", "Second level", "External review"], p=[0.82, 0.14, 0.04]),
                "appeal_status": status,
                "appeal_outcome": outcome,
                "appealed_amount": round(float(row.denied_amount), 2),
                "recovered_amount": round(recovered, 2),
                "days_to_appeal": days_to_appeal,
                "days_to_decision": days_to_decision if status == "Closed" else pd.NA,
                "appeal_success_flag": bool(success),
            }
        )
    return pd.DataFrame(rows)


def _appeal_success_probability(reason: str, preventable: bool) -> float:
    by_reason = {
        "Missing documentation": 0.58,
        "Coding error": 0.54,
        "Prior authorization missing": 0.42,
        "Medical necessity": 0.34,
        "Eligibility or coverage terminated": 0.28,
        "Timely filing": 0.24,
        "Out-of-network service": 0.22,
        "Duplicate claim": 0.18,
    }
    return min(0.72, by_reason.get(reason, 0.33) + (0.04 if preventable else 0.0))


def _make_revenue_leakage(
    claims: pd.DataFrame,
    denials: pd.DataFrame,
    appeals: pd.DataFrame,
    denial_reasons: pd.DataFrame,
) -> pd.DataFrame:
    if denials.empty:
        return pd.DataFrame()
    claim_lookup = claims.set_index("claim_key")
    reason_lookup = denial_reasons.set_index("denial_reason_key")
    appeal_recovery = appeals.groupby("denial_key")["recovered_amount"].sum() if not appeals.empty else pd.Series(dtype=float)
    appeal_success = appeals.groupby("denial_key")["appeal_success_flag"].max() if not appeals.empty else pd.Series(dtype=bool)
    rows = []
    for row in denials.itertuples(index=False):
        claim = claim_lookup.loc[int(row.claim_key)]
        reason = reason_lookup.loc[int(row.denial_reason_key)]
        expected_recovery_probability = _appeal_success_probability(reason["denial_reason_category"], bool(reason["preventable_flag"]))
        recoverable_amount = float(row.denied_amount) * (0.86 if bool(reason["appealable_flag"]) else 0.18)
        recovered_amount = float(appeal_recovery.get(int(row.denial_key), 0.0))
        underpaid_amount = max(float(claim["expected_payment_amount"]) - float(claim["paid_amount"]) - float(row.denied_amount), 0.0)
        expected_recovery_value = recoverable_amount * expected_recovery_probability
        aging_weight = min(100.0, max(1.0, float(row.days_to_denial) * 2.2))
        priority = (
            0.42 * expected_recovery_value
            + 0.22 * expected_recovery_probability * 1000
            + 0.16 * (100 if bool(reason["preventable_flag"]) else 20)
            + 0.12 * (100 if bool(reason["appealable_flag"]) else 15)
            + 0.08 * aging_weight
        )
        writeoff = max(float(row.denied_amount) - recoverable_amount - recovered_amount, 0.0)
        rows.append(
            {
                "claim_key": int(row.claim_key),
                "denial_key": int(row.denial_key),
                "submitted_amount": round(float(claim["submitted_amount"]), 2),
                "expected_payment_amount": round(float(claim["expected_payment_amount"]), 2),
                "paid_amount": round(float(claim["paid_amount"]), 2),
                "denied_amount": round(float(row.denied_amount), 2),
                "underpaid_amount": round(underpaid_amount, 2),
                "recoverable_amount": round(recoverable_amount, 2),
                "writeoff_amount": round(writeoff, 2),
                "expected_recovery_probability": round(expected_recovery_probability, 4),
                "expected_recovery_value": round(expected_recovery_value, 2),
                "priority_score": round(priority, 2),
                "actual_recovered_amount": round(recovered_amount, 2),
                "appeal_success_flag": bool(appeal_success.get(int(row.denial_key), False)),
            }
        )
    return pd.DataFrame(rows)


def _apply_denial_statuses(
    claims: pd.DataFrame,
    denials: pd.DataFrame,
    appeals: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if denials.empty:
        return claims, denials
    denials = denials.copy()
    if appeals.empty:
        denials.loc[denials["appealable_flag"], "denial_status"] = "Appealable"
        return claims, denials

    appealed_status = appeals.groupby("denial_key")["appeal_status"].apply(
        lambda values: "Pending appeal" if "Pending" in set(values) else "Closed"
    )
    denials["denial_status"] = denials["denial_key"].map(appealed_status)
    denials.loc[denials["denial_status"].isna() & denials["appealable_flag"], "denial_status"] = "Appealable"
    denials.loc[denials["denial_status"].isna(), "denial_status"] = "Open"
    return claims, denials
