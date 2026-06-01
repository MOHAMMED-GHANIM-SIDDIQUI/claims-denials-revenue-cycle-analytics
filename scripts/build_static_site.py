from __future__ import annotations

import shutil
from pathlib import Path


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "README.md").exists() and (candidate / "src").exists():
            return candidate
    return current.parents[1]


def main() -> int:
    root = find_project_root()
    dashboard = root / "reports" / "dashboard" / "claims_denials_revenue_cycle_dashboard.html"
    if not dashboard.exists():
        print("Dashboard not found. Build it first with:")
        print("  python scripts\\run_claims_denials_pipeline.py")
        return 1

    dist = root / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    shutil.copy2(dashboard, dist / "index.html")
    (dist / ".nojekyll").write_text("", encoding="utf-8")

    for source_name in ["executive_summary.md", "data_quality_report.csv"]:
        source = root / "reports" / source_name
        if source.exists():
            shutil.copy2(source, dist / source_name)

    print(f"Static site ready: {dist}")
    print("Open dist\\index.html locally or deploy dist/ to GitHub Pages, Netlify, Vercel, or Cloudflare Pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

