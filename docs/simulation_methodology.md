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
