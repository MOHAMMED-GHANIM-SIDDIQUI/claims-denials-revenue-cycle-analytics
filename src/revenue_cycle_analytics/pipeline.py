from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import PipelineConfig, find_project_root
from .custom_data import load_custom_claims_dataset
from .data_generation import generate_dataset
from .documentation import write_project_docs
from .marts import build_marts
from .models import train_and_score_models
from .quality import run_quality_checks
from .reporting import render_dashboard, write_executive_summary, write_model_card
from .warehouse import ensure_output_dirs, export_csv_tables, write_sqlite_database


def run_pipeline(config: PipelineConfig) -> dict[str, object]:
    ensure_output_dirs(config.project_root)
    if config.custom_claims_csv:
        generated = load_custom_claims_dataset(config.custom_claims_csv, plan_year=config.plan_year)
    else:
        generated = generate_dataset(
            seed=config.seed,
            claim_count=config.claim_count,
            member_count=config.member_count,
            provider_count=config.provider_count,
            plan_year=config.plan_year,
        )
    base_tables = generated.as_tables()
    marts = build_marts(base_tables)
    all_tables = {**base_tables, **marts}

    write_sqlite_database(all_tables, config.sqlite_path)
    export_csv_tables(all_tables, config.data_processed_dir)
    model_outputs = train_and_score_models(base_tables, config.data_processed_dir)
    quality_report = run_quality_checks(base_tables, marts, model_outputs.metrics)
    quality_report.to_csv(config.reports_dir / "data_quality_report.csv", index=False)
    write_project_docs(config.docs_dir)
    write_model_card(model_outputs, config.model_card_path)
    render_dashboard(base_tables, marts, model_outputs, quality_report, config.dashboard_path)
    write_executive_summary(base_tables, marts, model_outputs, quality_report, config.summary_path)

    failures = int((quality_report["status"] == "FAIL").sum())
    return {
        "sqlite_path": config.sqlite_path,
        "dashboard_path": config.dashboard_path,
        "summary_path": config.summary_path,
        "quality_failures": failures,
        "quality_report": quality_report,
        "table_count": len(all_tables),
        "claim_count": len(base_tables["fact_claim"]),
        "denial_count": len(base_tables["fact_denial"]),
        "appeal_count": len(base_tables["fact_appeal"]),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Claims Denials Revenue Cycle Analytics project.")
    parser.add_argument("--project-root", type=Path, default=find_project_root(), help="Repository/project root.")
    parser.add_argument("--claims", type=int, default=12_000, help="Number of simulated claims to generate.")
    parser.add_argument("--members", type=int, default=4_500, help="Number of simulated members.")
    parser.add_argument("--providers", type=int, default=180, help="Number of simulated providers.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation.")
    parser.add_argument("--plan-year", type=int, default=2025, help="Plan year for the synthetic benchmark and claims.")
    parser.add_argument("--custom-claims", type=Path, default=None, help="Optional custom claims CSV to use instead of generated sample data.")
    parser.add_argument("--allow-quality-failures", action="store_true", help="Return success even if quality checks fail.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = PipelineConfig(
        project_root=args.project_root.resolve(),
        seed=args.seed,
        claim_count=args.claims,
        member_count=args.members,
        provider_count=args.providers,
        plan_year=args.plan_year,
        custom_claims_csv=args.custom_claims.resolve() if args.custom_claims else None,
    )
    result = run_pipeline(config)
    print("Claims Denials Revenue Cycle Analytics build complete")
    print(f"Claims: {result['claim_count']:,}")
    print(f"Denials: {result['denial_count']:,}")
    print(f"Appeals: {result['appeal_count']:,}")
    print(f"Tables exported: {result['table_count']}")
    print(f"SQLite warehouse: {result['sqlite_path']}")
    print(f"Dashboard: {result['dashboard_path']}")
    print(f"Executive summary: {result['summary_path']}")
    print(f"Quality failures: {result['quality_failures']}")
    if result["quality_failures"] and not args.allow_quality_failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
