from __future__ import annotations

from pathlib import Path


def write_project_docs(docs_dir: Path) -> list[Path]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    docs = {
        "simulation_methodology.md": _SIMULATION_METHODOLOGY,
        "data_dictionary.md": _DATA_DICTIONARY,
        "kpi_dictionary.md": _KPI_DICTIONARY,
        "data_sources.md": _DATA_SOURCES,
        "dashboard_spec.md": _DASHBOARD_SPEC,
    }
    written = []
    for name, content in docs.items():
        path = docs_dir / name
        path.write_text(content.strip() + "\n", encoding="utf-8")
        written.append(path)
    return written


_SIMULATION_METHODOLOGY = """
# Simulation Methodology

Claim-level denial events in this project are simulated from synthetic claims using transparent business rules and calibrated against public benchmark-style aggregate denial rates. They are not real patient, provider, or payer adjudication records.

## Inputs

- Plan-level benchmark denial, appeal, upheld, and overturn rates
- Synthetic member-plan assignment
- Synthetic providers, services, and contract rates
- Claim amount, network status, authorization, documentation, timely filing, duplicate, and coverage flags

## Denial Rule Order

1. Inactive coverage creates an eligibility denial.
2. Duplicate claim creates a duplicate denial.
3. Late filing creates a timely filing denial.
4. Missing required authorization creates a prior authorization denial.
5. Missing required documentation creates a documentation denial.
6. Remaining claims are selected by risk score until plan-level denial rates are close to benchmark targets.

## Appeal and Recovery Logic

Appeal likelihood increases with denied amount, appealability, preventability, and higher-dollar service lines. Successful appeals recover a portion of denied amount. Work queue priority is based on expected recovery value, appeal probability, preventability, appealability, and aging.
"""

_DATA_DICTIONARY = """
# Data Dictionary

## Core Tables

| Table | Grain | Purpose |
|---|---|---|
| dim_issuer | Issuer | Payer identity and state context |
| dim_plan | Plan year | Plan, metal level, market, and network type |
| dim_member_simulated | Synthetic member | Coverage, risk, and plan assignment |
| dim_provider | Provider | NPI-like provider, specialty, and network status |
| dim_service | Service line | Procedure/service group with auth and documentation risk |
| dim_denial_reason | Denial reason | Reason taxonomy, owner, root cause, preventability |
| fact_claim | Claim | Submitted, allowed, expected, paid, denied, and adjudication fields |
| fact_denial | Denial | Denied amount, reason, owner, preventability, and status |
| fact_appeal | Appeal event | Appeal dates, outcome, recovered amount, and success flag |
| fact_revenue_leakage | Denial | Recoverable amount, expected recovery value, write-off, and priority |

## Marts

| Mart | Purpose |
|---|---|
| mart_denial_rate | Denial rate by payer, plan, state, service line, and network |
| mart_appeal_performance | Appeal filing, success, recovery, and decision timing |
| mart_revenue_leakage | Recoverable amount and expected recovery by payer/service/reason |
| mart_denial_work_queue | Operational queue ranked by priority score |
| mart_payer_scorecard | Payer friction score and contracting review signal |
| mart_service_line_denials | Service-line denial and recovery opportunity |
| mart_underpayment_opportunity | Paid amount vs expected or negotiated-rate opportunity |
"""

_KPI_DICTIONARY = """
# KPI Dictionary

| KPI | Formula | Owner |
|---|---|---|
| Claims received | Count of fact_claim rows | Claims ops |
| Denied claims | Count of fact_denial rows | Revenue cycle |
| Denial rate | Denied claims / claims received | Revenue cycle |
| Denied amount | Sum of fact_denial.denied_amount | Finance |
| Preventable denial rate | Preventable denials / denied claims | Revenue cycle |
| Appeal rate | Appeals filed / denied claims | Appeals team |
| Appeal success rate | Successful appeals / appeals filed | Appeals team |
| Recovered amount | Sum of appeal recovered amount | Finance |
| Recoverable amount | Denied amount adjusted for appealability | Finance |
| Expected recovery value | Recoverable amount * expected recovery probability | Finance |
| Underpaid amount | Contract or expected amount - paid amount | Contracting |
| Payer friction score | Weighted denial, upheld, aging, underpayment, documentation score | Managed care |
| Work queue priority score | Weighted expected recovery, probability, preventability, appealability, aging | Operations |
"""

_DATA_SOURCES = """
# Data Sources

This runnable build ships with synthetic data generation so it works without downloading large public files. The structure is designed to be replaced with public CMS inputs.

## Public Sources To Use In A Production Extension

- CMS Health Insurance Exchange Public Use Files: https://www.cms.gov/marketplace/resources/data/public-use-files
- CMS Transparency in Coverage PUF: https://catalog.data.gov/dataset/transparency-in-coverage-puf-py2026
- CMS Synthetic Medicare Claims PUFs: https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files
- CMS Hospital Price Transparency: https://www.cms.gov/priorities/key-initiatives/hospital-price-transparency
- CMS NPPES NPI Files: https://download.cms.gov/nppes/NPI_Files.html

## Current Build Mode

- `fact_denial_benchmark` represents benchmark-style aggregate payer/plan rates.
- `fact_claim`, `fact_denial`, and `fact_appeal` are simulated.
- `fact_contract_rate` is a focused price-transparency-style sample with confidence scores.
"""

_DASHBOARD_SPEC = """
# Dashboard Specification

The generated dashboard is `reports/dashboard/claims_denials_revenue_cycle_dashboard.html`.

## Included Views

- Executive KPI strip
- Denial reason Pareto
- Payer friction matrix
- Service-line recovery opportunity
- Appeal outcome mix
- Denial risk score distribution
- Priority denial work queue
- Underpayment opportunity table
- Model driver table
- Data quality gate

## Dashboard Users

- Revenue cycle director
- Denials analyst
- Claims operations leader
- Managed care contracting analyst
- Healthcare BI analyst
"""

