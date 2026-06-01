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
