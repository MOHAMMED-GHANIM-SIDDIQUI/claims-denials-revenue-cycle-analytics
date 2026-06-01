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
