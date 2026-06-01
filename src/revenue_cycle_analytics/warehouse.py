from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def ensure_output_dirs(project_root: Path) -> None:
    for path in [
        project_root / "data" / "processed",
        project_root / "reports",
        project_root / "reports" / "dashboard",
        project_root / "reports" / "figures",
        project_root / "docs",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def write_sqlite_database(tables: dict[str, pd.DataFrame], sqlite_path: Path) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        for name, frame in tables.items():
            frame.to_sql(name, conn, if_exists="replace", index=False)
        _create_indexes(conn)
        conn.commit()
    finally:
        conn.close()


def export_csv_tables(tables: dict[str, pd.DataFrame], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, frame in tables.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths


def _create_indexes(conn: sqlite3.Connection) -> None:
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_fact_claim_plan ON fact_claim(plan_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_claim_issuer ON fact_claim(issuer_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_claim_service ON fact_claim(service_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_denial_claim ON fact_denial(claim_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_appeal_denial ON fact_appeal(denial_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_revenue_leakage_denial ON fact_revenue_leakage(denial_key)",
    ]
    for statement in index_statements:
        conn.execute(statement)
