# GitHub Publication Checklist

Use this before pushing the project to a public repository.

## Must Keep

- `README.md`
- `requirements.txt`
- `pyproject.toml`
- `src/revenue_cycle_analytics/`
- `scripts/run_claims_denials_pipeline.py`
- `scripts/serve_dashboard.py`
- `scripts/build_static_site.py`
- `.github/workflows/deploy-pages.yml`
- `tests/`
- `sql/`
- `docs/`
- `reports/dashboard/claims_denials_revenue_cycle_dashboard.html`
- `reports/executive_summary.md`
- `reports/data_quality_report.csv`

## Generated Files

The pipeline can regenerate everything under `data/processed/` and `reports/dashboard/`.

The SQLite warehouse file is ignored by `.gitignore` because it is generated and can grow quickly:

```text
data/processed/claims_denials_revenue_cycle.db
```

CSV marts and reports are safe to publish because they are synthetic and contain no PHI.

## Public README Talking Points

- The project uses simulated claim-level adjudication data.
- Public CMS denial data is aggregate, so claim-level denials are not represented as real adjudication records.
- The value of the project is the analytics architecture: denial simulation, appeal prioritization, revenue leakage, payer scorecards, work queues, data-quality gates, and model scoring.
- The dashboard is standalone HTML and can be opened directly or served locally.

## Pre-Push Verification

Run:

```powershell
python scripts\run_claims_denials_pipeline.py
python -m pytest
python scripts\build_static_site.py
python scripts\serve_dashboard.py
```

Then open:

```text
http://127.0.0.1:8055/reports/dashboard/claims_denials_revenue_cycle_dashboard.html
```

## Free Deployment

Use GitHub Pages:

1. Push the repository to GitHub.
2. Open repository Settings.
3. Open Pages.
4. Set source to GitHub Actions.
5. Push to `main` or `master`, or run the workflow manually.

The workflow rebuilds the project, runs tests, creates `dist/index.html`, and publishes it.
