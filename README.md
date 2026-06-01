# Claims Denials, Appeals & Revenue Cycle Intelligence Platform

Runnable healthcare revenue cycle analytics project for denial operations, appeal prioritization, payer friction, underpayment opportunity, and recovery work queues.

The repository still includes the original healthcare analytics blueprints, but the Claims Denials project is now implemented as an end-to-end Python pipeline.

## What It Builds

- Transparent simulated claim-level adjudication data calibrated to benchmark-style denial rates
- SQLite analytics warehouse with dimensions, facts, marts, model scores, and quality outputs
- CSV exports for BI tools and portfolio review
- Denial rate, appeal performance, revenue leakage, payer scorecard, service-line, work queue, and underpayment marts
- Denial risk and appeal success scoring models
- Data-quality gate with pass/fail checks
- Interactive standalone HTML dashboard with search, filters, sorting, queue triage, local state, CSV export, and dark/light mode
- Executive summary, KPI dictionary, data dictionary, dashboard spec, and model cards

## Simulation Disclaimer

Claim-level denial events in this project are simulated from synthetic claims using transparent business rules and calibrated against public benchmark-style aggregate denial rates. They are not real patient, provider, or payer adjudication records.

## Quick Start

Create and activate a virtual environment if you want an isolated setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Build the complete analytics project:

```powershell
python scripts\run_claims_denials_pipeline.py
```

Useful options:

```powershell
python scripts\run_claims_denials_pipeline.py --claims 20000 --seed 42
python scripts\run_claims_denials_pipeline.py --claims 5000 --allow-quality-failures
python scripts\run_claims_denials_pipeline.py --custom-claims data\raw\custom_claims_template.csv
```

Run tests:

```powershell
python -m pytest
```

## Run Locally

After building the project, serve the dashboard locally:

```powershell
python scripts\serve_dashboard.py
```

Open:

```text
http://127.0.0.1:8055/reports/dashboard/claims_denials_revenue_cycle_dashboard.html
```

The dashboard is also standalone, so it can be opened directly from `reports/dashboard/claims_denials_revenue_cycle_dashboard.html`.

## Interactive App Features

- Search and filter the denial work queue by payer, service line, denial reason, and text.
- Sort work queue and underpayment tables by clicking column headers.
- Flag, resolve, and reopen denial queue items. Triage state is saved in browser `localStorage`.
- Export the current filtered queue or underpayment opportunities as CSV.
- Open row-level claim details in a governance-aware modal.
- Toggle premium dark and light themes.

## Use Custom Data

You can rebuild the same dashboard from your own claims CSV:

```powershell
python scripts\run_claims_denials_pipeline.py --custom-claims path\to\your_claims.csv
python scripts\serve_dashboard.py
```

The importer accepts flexible column names such as `payer`, `payer_name`, `issuer_name`, `claim_status`, `denial_reason`, `submitted_amount`, `expected_payment_amount`, `paid_amount`, and `service_line`.

See [Custom Data Guide](docs/custom_data_guide.md) and the sample template at `data/raw/custom_claims_template.csv`.

## Deploy Free

This project is deploy-ready as a static site, so it can run free on GitHub Pages.

Build the deployable site locally:

```powershell
python scripts\run_claims_denials_pipeline.py
python scripts\build_static_site.py
```

Then open:

```text
dist/index.html
```

For GitHub Pages, the workflow at `.github/workflows/deploy-pages.yml` will:

1. Install Python dependencies.
2. Rebuild the analytics dashboard.
3. Run tests.
4. Build `dist/index.html`.
5. Deploy the static app to GitHub Pages.

After pushing to GitHub, enable GitHub Pages with source set to **GitHub Actions** in the repository settings.

## Main Outputs

- SQLite warehouse: `data/processed/claims_denials_revenue_cycle.db`
- Dashboard: `reports/dashboard/claims_denials_revenue_cycle_dashboard.html`
- Executive summary: `reports/executive_summary.md`
- Quality report: `reports/data_quality_report.csv`
- Model metrics: `data/processed/model_metrics.json`
- Work queue mart: `data/processed/mart_denial_work_queue.csv`
- Payer scorecard mart: `data/processed/mart_payer_scorecard.csv`

## Repository Map

```text
src/revenue_cycle_analytics/
  data_generation.py   # synthetic claims, denials, appeals, rates
  marts.py             # governed analytics marts
  models.py            # denial risk and appeal success models
  quality.py           # data-quality checks
  reporting.py         # dashboard and executive summary rendering
  pipeline.py          # orchestration CLI

scripts/
  run_claims_denials_pipeline.py
  serve_dashboard.py
  build_static_site.py

sql/05_marts/
  claims_denials_marts.sql

tests/
  test_pipeline.py
```

## Blueprint References

- [Claims Denials Revenue Cycle Blueprint](docs/Claims_Denials_Revenue_Cycle_Analytics_Blueprint.md)
- [Healthcare Claims Intelligence Blueprint](docs/Healthcare_Claims_Intelligence_Project_Blueprint.md)
- [Provider Network Value-Based Care Blueprint](docs/Provider_Network_Value_Based_Care_Analytics_Blueprint.md)
- [GitHub Publication Checklist](docs/github_publication_checklist.md)

Designed PDF/HTML blueprint exports remain in `reports/pdf/`.
