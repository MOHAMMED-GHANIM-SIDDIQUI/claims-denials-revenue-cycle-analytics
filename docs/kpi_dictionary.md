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
