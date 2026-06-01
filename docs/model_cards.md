# Model Cards

## Denial Risk Model

- Target: `denied_flag`
- Model type: RandomForestClassifier
- Training rows: 9000
- Test rows: 3000
- ROC-AUC: 0.9074
- Average precision: 0.6882
- Precision at top decile: 0.7167
- Recall at top decile: 0.4361

Business use: prioritize pre-bill edits for high-risk claims before submission.

## Appeal Success Model

- Target: `appeal_success_flag`
- Model type: RandomForestClassifier
- Training rows: 590
- Test rows: 197
- ROC-AUC: 0.6231
- Average precision: 0.4328
- Precision at top decile: 0.3
- Recall at top decile: 0.087

Business use: rank denials by expected recovery value and appeal success probability.

## Limitations

- Claim-level denial labels are simulated for portfolio and workflow demonstration.
- Public aggregate denial data does not expose real claim-line adjudication events.
- Price transparency matching is represented by a confidence-scored simulated sample.
- Model metrics should be interpreted as pipeline validation evidence, not production payer behavior.
