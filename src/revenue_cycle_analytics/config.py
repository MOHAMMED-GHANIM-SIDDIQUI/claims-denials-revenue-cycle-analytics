from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Find the repository root by walking up to README.md and docs."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "README.md").exists() and (candidate / "docs").exists():
            return candidate
    return current


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    seed: int = 42
    claim_count: int = 12_000
    member_count: int = 4_500
    provider_count: int = 180
    plan_year: int = 2025
    custom_claims_csv: Path | None = None

    @classmethod
    def default(cls) -> "PipelineConfig":
        return cls(project_root=find_project_root())

    @property
    def data_processed_dir(self) -> Path:
        return self.project_root / "data" / "processed"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "reports"

    @property
    def dashboard_dir(self) -> Path:
        return self.reports_dir / "dashboard"

    @property
    def figures_dir(self) -> Path:
        return self.reports_dir / "figures"

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    @property
    def sqlite_path(self) -> Path:
        return self.data_processed_dir / "claims_denials_revenue_cycle.db"

    @property
    def dashboard_path(self) -> Path:
        return self.dashboard_dir / "claims_denials_revenue_cycle_dashboard.html"

    @property
    def summary_path(self) -> Path:
        return self.reports_dir / "executive_summary.md"

    @property
    def model_card_path(self) -> Path:
        return self.docs_dir / "model_cards.md"
