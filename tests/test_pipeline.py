from __future__ import annotations

import sqlite3

from revenue_cycle_analytics.config import PipelineConfig
from revenue_cycle_analytics.data_generation import generate_dataset
from revenue_cycle_analytics.marts import build_marts
from revenue_cycle_analytics.models import train_and_score_models
from revenue_cycle_analytics.pipeline import run_pipeline
from revenue_cycle_analytics.quality import run_quality_checks


def test_generated_dataset_has_revenue_cycle_integrity(tmp_path):
    generated = generate_dataset(seed=101, claim_count=1_800, member_count=650, provider_count=55)
    tables = generated.as_tables()
    marts = build_marts(tables)
    model_outputs = train_and_score_models(tables, tmp_path)
    quality = run_quality_checks(tables, marts, model_outputs.metrics)

    assert len(tables["fact_claim"]) == 1_800
    assert not tables["fact_denial"].empty
    assert not tables["fact_appeal"].empty
    assert not marts["mart_denial_work_queue"].empty
    assert (quality["status"] == "FAIL").sum() == 0


def test_end_to_end_pipeline_writes_warehouse_dashboard_and_marts(tmp_path):
    config = PipelineConfig(
        project_root=tmp_path,
        seed=202,
        claim_count=2_200,
        member_count=800,
        provider_count=70,
        plan_year=2025,
    )
    result = run_pipeline(config)

    assert result["quality_failures"] == 0
    assert config.sqlite_path.exists()
    assert config.dashboard_path.exists()
    assert config.summary_path.exists()
    assert (config.data_processed_dir / "mart_denial_work_queue.csv").exists()
    assert (config.data_processed_dir / "model_claim_denial_scores.csv").exists()

    conn = sqlite3.connect(config.sqlite_path)
    try:
        table_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        claim_count = conn.execute("SELECT COUNT(*) FROM fact_claim").fetchone()[0]
        work_queue_count = conn.execute("SELECT COUNT(*) FROM mart_denial_work_queue").fetchone()[0]
    finally:
        conn.close()

    assert table_count >= 18
    assert claim_count == 2_200
    assert work_queue_count > 0


def test_pipeline_accepts_custom_claims_csv(tmp_path):
    custom_csv = tmp_path / "custom_claims.csv"
    custom_csv.write_text(
        "\n".join(
            [
                "claim_id,payer,plan_name,provider_name,service_line,claim_status,denial_reason,submitted_amount,expected_payment_amount,paid_amount,claim_received_date,adjudication_date,appeal_outcome,recovered_amount",
                "A1,Apex Health,Apex Silver,Metro Hospital,Inpatient,Denied,Coding error,12000,7200,0,2025-01-01,2025-01-12,Appeal overturned,6000",
                "A2,Apex Health,Apex Silver,Metro Hospital,Outpatient surgery,Paid,,5000,3000,3000,2025-01-02,2025-01-14,,",
                "B1,BrightPath,BrightPath HMO,Valley Imaging,Imaging,Denied,Prior authorization missing,1500,900,0,2025-01-04,2025-01-18,Appeal upheld,0",
                "B2,BrightPath,BrightPath HMO,Valley Imaging,Imaging,Paid,,1400,850,820,2025-01-05,2025-01-19,,",
            ]
        ),
        encoding="utf-8",
    )
    config = PipelineConfig(
        project_root=tmp_path,
        custom_claims_csv=custom_csv,
        plan_year=2025,
    )

    result = run_pipeline(config)

    assert result["quality_failures"] == 0
    assert result["claim_count"] == 4
    assert result["denial_count"] == 2
    assert config.dashboard_path.exists()

    conn = sqlite3.connect(config.sqlite_path)
    try:
        payers = {row[0] for row in conn.execute("SELECT DISTINCT issuer_name FROM dim_issuer")}
        work_queue_count = conn.execute("SELECT COUNT(*) FROM mart_denial_work_queue").fetchone()[0]
    finally:
        conn.close()

    assert payers == {"Apex Health", "BrightPath"}
    assert work_queue_count == 2
