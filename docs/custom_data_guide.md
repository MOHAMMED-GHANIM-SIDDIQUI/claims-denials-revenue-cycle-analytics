# Custom Data Guide

You can rebuild the project with your own claims CSV.

## Run With Custom Data

```powershell
python scripts\run_claims_denials_pipeline.py --custom-claims data\raw\custom_claims_template.csv
python scripts\serve_dashboard.py
```

Then open:

```text
http://127.0.0.1:8055/reports/dashboard/claims_denials_revenue_cycle_dashboard.html
```

## Flexible Column Names

The importer accepts common aliases. For example:

| Canonical field | Accepted aliases |
|---|---|
| `claim_id` | `claim_number`, `claim`, `claim_no` |
| `issuer_name` | `payer`, `payer_name`, `insurer`, `carrier` |
| `plan_name` | `plan`, `insurance_plan` |
| `provider_name` | `provider`, `facility`, `billing_provider` |
| `service_line` | `service`, `department`, `specialty` |
| `claim_status` | `status`, `adjudication_status` |
| `denial_reason_category` | `denial_reason`, `denial_category`, `reason`, `denial_code` |
| `submitted_amount` | `billed_amount`, `charge_amount`, `claims_amount` |
| `paid_amount` | `paid`, `payment_amount`, `reimbursed_amount` |
| `claim_received_date` | `received_date`, `submitted_date`, `claim_date` |
| `adjudication_date` | `processed_date`, `decision_date` |

## Recommended Minimum Columns

Use these for the best dashboard:

```text
claim_id,payer,plan_name,provider_name,service_line,claim_status,denial_reason,submitted_amount,expected_payment_amount,paid_amount,claim_received_date,adjudication_date
```

## What Happens If Columns Are Missing

- Missing payer becomes `Custom Payer`.
- Missing plan becomes `{payer} Standard Plan`.
- Missing service line becomes `Professional E/M`.
- Missing claim status is inferred from denial reason and payment fields.
- Missing expected payment is estimated from allowed/submitted amount.
- Missing denial reason for denied claims becomes `Coding error`.
- Missing appeal data is allowed; the appeal model falls back gracefully.

## Privacy Note

Do not upload real PHI to a public GitHub repository. If your file contains real claim/member/provider data, de-identify it before publishing.

