-- SQLite-compatible reference mart definitions.
-- The production pipeline builds these marts with pandas and exports them to
-- SQLite/CSV. These views document the business logic in query form.

CREATE VIEW IF NOT EXISTS mart_denial_rate_sql AS
SELECT
    i.issuer_name,
    p.plan_name,
    i.state_code,
    s.service_line,
    c.network_status,
    COUNT(DISTINCT c.claim_key) AS claims_received,
    COUNT(DISTINCT d.denial_key) AS denied_claims,
    SUM(COALESCE(d.denied_amount, 0)) AS denied_amount,
    CAST(COUNT(DISTINCT d.denial_key) AS REAL) / NULLIF(COUNT(DISTINCT c.claim_key), 0) AS denial_rate,
    SUM(CASE WHEN d.preventable_flag = 1 THEN 1 ELSE 0 END) AS preventable_denials
FROM fact_claim c
JOIN dim_issuer i ON c.issuer_key = i.issuer_key
JOIN dim_plan p ON c.plan_key = p.plan_key
JOIN dim_service s ON c.service_key = s.service_key
LEFT JOIN fact_denial d ON c.claim_key = d.claim_key
GROUP BY
    i.issuer_name,
    p.plan_name,
    i.state_code,
    s.service_line,
    c.network_status;

CREATE VIEW IF NOT EXISTS mart_denial_work_queue_sql AS
SELECT
    c.claim_id,
    i.issuer_name,
    p.plan_name,
    pr.provider_name,
    s.service_line,
    dr.denial_reason_category,
    d.denied_amount,
    rl.recoverable_amount,
    rl.expected_recovery_probability,
    rl.expected_recovery_value,
    rl.priority_score,
    CASE
        WHEN dr.denial_reason_category = 'Missing documentation' THEN 'Submit documentation packet'
        WHEN dr.denial_reason_category = 'Prior authorization missing' THEN 'Validate authorization and appeal if supported'
        WHEN dr.denial_reason_category = 'Coding error' THEN 'Correct and resubmit'
        WHEN dr.denial_reason_category = 'Medical necessity' THEN 'Clinical appeal review'
        WHEN dr.denial_reason_category = 'Eligibility or coverage terminated' THEN 'Eligibility verification'
        WHEN dr.denial_reason_category = 'Timely filing' THEN 'Late filing exception review'
        ELSE 'Analyst review'
    END AS recommended_action
FROM fact_denial d
JOIN fact_claim c ON d.claim_key = c.claim_key
JOIN dim_issuer i ON c.issuer_key = i.issuer_key
JOIN dim_plan p ON c.plan_key = p.plan_key
JOIN dim_provider pr ON c.provider_key = pr.provider_key
JOIN dim_service s ON c.service_key = s.service_key
JOIN dim_denial_reason dr ON d.denial_reason_key = dr.denial_reason_key
LEFT JOIN fact_revenue_leakage rl ON d.denial_key = rl.denial_key
WHERE d.denial_status IN ('Open', 'Appealable', 'Pending appeal', 'Pending review');

CREATE VIEW IF NOT EXISTS mart_payer_scorecard_sql AS
WITH payer_claims AS (
    SELECT
        i.issuer_key,
        i.issuer_name,
        COUNT(DISTINCT c.claim_key) AS claims_received,
        SUM(c.expected_payment_amount) AS expected_payment_amount
    FROM fact_claim c
    JOIN dim_issuer i ON c.issuer_key = i.issuer_key
    GROUP BY i.issuer_key, i.issuer_name
),
payer_denials AS (
    SELECT
        c.issuer_key,
        COUNT(DISTINCT d.denial_key) AS denied_claims,
        SUM(d.denied_amount) AS denied_amount,
        AVG(d.days_to_denial) AS avg_days_to_denial
    FROM fact_denial d
    JOIN fact_claim c ON d.claim_key = c.claim_key
    GROUP BY c.issuer_key
)
SELECT
    pc.issuer_name,
    pc.claims_received,
    COALESCE(pd.denied_claims, 0) AS denied_claims,
    COALESCE(pd.denied_amount, 0) AS denied_amount,
    CAST(COALESCE(pd.denied_claims, 0) AS REAL) / NULLIF(pc.claims_received, 0) AS denial_rate,
    COALESCE(pd.avg_days_to_denial, 0) AS avg_days_to_denial
FROM payer_claims pc
LEFT JOIN payer_denials pd ON pc.issuer_key = pd.issuer_key;

