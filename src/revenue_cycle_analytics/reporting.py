from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline.offline import get_plotlyjs
from jinja2 import Template

from .models import ModelOutputs


def render_dashboard(
    tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    model_outputs: ModelOutputs,
    quality_report: pd.DataFrame,
    dashboard_path: Path,
) -> Path:
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    kpis = _kpis(tables, marts)
    figures = _figures(tables, marts, model_outputs)
    work_queue_frame = marts["mart_denial_work_queue"].head(500).copy()
    underpayment_frame = marts["mart_underpayment_opportunity"].head(500).copy()
    work_queue = work_queue_frame.to_dict("records")
    underpayment = underpayment_frame.to_dict("records")
    html = Template(_DASHBOARD_TEMPLATE).render(
        kpis=kpis,
        figures=figures,
        work_queue=work_queue,
        underpayment=underpayment,
        quality=quality_report.to_dict("records"),
        top_features=model_outputs.feature_importance.head(14).to_dict("records"),
        plotly_js=get_plotlyjs(),
        work_queue_json=work_queue_frame.to_json(orient="records"),
        underpayment_json=underpayment_frame.to_json(orient="records"),
    )
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path


def write_executive_summary(
    tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    model_outputs: ModelOutputs,
    quality_report: pd.DataFrame,
    summary_path: Path,
) -> Path:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    kpis = _kpis(tables, marts)
    payer = marts["mart_payer_scorecard"].iloc[0]
    reason = (
        tables["fact_denial"]
        .merge(tables["dim_denial_reason"], on="denial_reason_key")
        .groupby("denial_reason_category")["denied_amount"]
        .sum()
        .sort_values(ascending=False)
        .head(1)
    )
    service = marts["mart_service_line_denials"].iloc[0]
    denial_auc = model_outputs.metrics["denial_risk_model"].get("roc_auc")
    appeal_auc = model_outputs.metrics["appeal_success_model"].get("roc_auc")
    failed_checks = int((quality_report["status"] == "FAIL").sum())
    content = f"""# Executive Summary - Claims Denials Revenue Cycle Analytics

## Portfolio Build Status

The project is now runnable end to end. It generates a transparent simulated claim-level adjudication layer, writes a SQLite analytics warehouse, exports governed marts, trains denial and appeal scoring models, runs data-quality checks, and renders an operational HTML dashboard.

## Operating Snapshot

- Claims received: {kpis['claims_received']:,}
- Denied claims: {kpis['denied_claims']:,}
- Denial rate: {kpis['denial_rate']:.1%}
- Denied amount: ${kpis['denied_amount']:,.0f}
- Recoverable amount: ${kpis['recoverable_amount']:,.0f}
- Expected recovery value: ${kpis['expected_recovery_value']:,.0f}
- Appeal success rate: {kpis['appeal_success_rate']:.1%}
- Open work queue items: {kpis['open_work_queue']:,}

## Key Findings

- Highest payer friction: {payer['issuer_name']} with a friction score of {payer['payer_friction_score']:.2f}.
- Largest denied-amount reason: {reason.index[0]} at ${reason.iloc[0]:,.0f}.
- Largest service-line recovery opportunity: {service['service_line']} with ${service['expected_recovery_value']:,.0f} expected recovery value.
- Denial risk model ROC-AUC: {denial_auc if denial_auc is not None else 'not available'}.
- Appeal success model ROC-AUC: {appeal_auc if appeal_auc is not None else 'baseline mode'}.
- Data-quality failures: {failed_checks}.

## Simulation Disclaimer

Claim-level denial events are simulated from synthetic claims using transparent business rules and calibrated against public benchmark-style aggregate denial rates. They are not real patient, provider, or payer adjudication records.
"""
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


def write_model_card(model_outputs: ModelOutputs, model_card_path: Path) -> Path:
    model_card_path.parent.mkdir(parents=True, exist_ok=True)
    denial = model_outputs.metrics["denial_risk_model"]
    appeal = model_outputs.metrics["appeal_success_model"]
    content = f"""# Model Cards

## Denial Risk Model

- Target: `denied_flag`
- Model type: {denial.get('model_type')}
- Training rows: {denial.get('rows_trained')}
- Test rows: {denial.get('rows_tested')}
- ROC-AUC: {denial.get('roc_auc')}
- Average precision: {denial.get('average_precision')}
- Precision at top decile: {denial.get('precision_at_top_decile')}
- Recall at top decile: {denial.get('recall_at_top_decile')}

Business use: prioritize pre-bill edits for high-risk claims before submission.

## Appeal Success Model

- Target: `appeal_success_flag`
- Model type: {appeal.get('model_type')}
- Training rows: {appeal.get('rows_trained')}
- Test rows: {appeal.get('rows_tested')}
- ROC-AUC: {appeal.get('roc_auc')}
- Average precision: {appeal.get('average_precision')}
- Precision at top decile: {appeal.get('precision_at_top_decile')}
- Recall at top decile: {appeal.get('recall_at_top_decile')}

Business use: rank denials by expected recovery value and appeal success probability.

## Limitations

- Claim-level denial labels are simulated for portfolio and workflow demonstration.
- Public aggregate denial data does not expose real claim-line adjudication events.
- Price transparency matching is represented by a confidence-scored simulated sample.
- Model metrics should be interpreted as pipeline validation evidence, not production payer behavior.
"""
    model_card_path.write_text(content, encoding="utf-8")
    return model_card_path


def _kpis(tables: dict[str, pd.DataFrame], marts: dict[str, pd.DataFrame]) -> dict[str, float | int]:
    claim = tables["fact_claim"]
    denial = tables["fact_denial"]
    appeal = tables["fact_appeal"]
    leakage = tables["fact_revenue_leakage"]
    underpayment = marts["mart_underpayment_opportunity"]
    return {
        "claims_received": int(claim["claim_key"].nunique()),
        "denied_claims": int(denial["denial_key"].nunique()),
        "denial_rate": float(denial["denial_key"].nunique() / claim["claim_key"].nunique()),
        "denied_amount": float(denial["denied_amount"].sum()),
        "recoverable_amount": float(leakage["recoverable_amount"].sum()),
        "expected_recovery_value": float(leakage["expected_recovery_value"].sum()),
        "appeal_success_rate": float(appeal["appeal_success_flag"].mean()) if not appeal.empty else 0.0,
        "recovered_amount": float(appeal["recovered_amount"].sum()) if not appeal.empty else 0.0,
        "underpaid_amount": float(underpayment["underpaid_amount"].sum()) if not underpayment.empty else 0.0,
        "open_work_queue": int(len(marts["mart_denial_work_queue"])),
    }


def _figures(tables: dict[str, pd.DataFrame], marts: dict[str, pd.DataFrame], model_outputs: ModelOutputs) -> dict[str, str]:
    denial_reason = (
        tables["fact_denial"]
        .merge(tables["dim_denial_reason"], on="denial_reason_key")
        .groupby("denial_reason_category", as_index=False)
        .agg(denials=("denial_key", "nunique"), denied_amount=("denied_amount", "sum"))
        .sort_values("denied_amount", ascending=False)
        .head(10)
    )
    reason_fig = px.bar(
        denial_reason,
        x="denied_amount",
        y="denial_reason_category",
        color="denials",
        orientation="h",
        color_continuous_scale=["#38BDF8", "#F59E0B", "#EF4444"],
        labels={"denied_amount": "Denied amount", "denial_reason_category": ""},
    )
    reason_fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=410)

    payer = marts["mart_payer_scorecard"].copy()
    payer_fig = px.scatter(
        payer,
        x="denial_rate",
        y="appeal_upheld_rate",
        size="denied_amount",
        color="friction_tier",
        hover_name="issuer_name",
        color_discrete_sequence=["#0EA5E9", "#14B8A6", "#F59E0B", "#EF4444"],
        labels={"denial_rate": "Denial rate", "appeal_upheld_rate": "Appeal upheld rate"},
    )
    payer_fig.update_layout(height=410)

    service_fig = px.bar(
        marts["mart_service_line_denials"].sort_values("expected_recovery_value", ascending=True),
        x="expected_recovery_value",
        y="service_line",
        color="denial_rate",
        orientation="h",
        color_continuous_scale=["#22C55E", "#F59E0B", "#DC2626"],
        labels={"expected_recovery_value": "Expected recovery value", "service_line": ""},
    )
    service_fig.update_layout(height=410)

    appeal = tables["fact_appeal"]
    if appeal.empty:
        appeal_fig = go.Figure()
    else:
        outcome = appeal.groupby("appeal_outcome", as_index=False).agg(appeals=("appeal_key", "nunique"), recovered_amount=("recovered_amount", "sum"))
        appeal_fig = px.bar(
            outcome,
            x="appeal_outcome",
            y="appeals",
            color="recovered_amount",
            color_continuous_scale=["#94A3B8", "#22C55E"],
            labels={"appeal_outcome": "", "appeals": "Appeals"},
        )
    appeal_fig.update_layout(height=360)

    risk = model_outputs.claim_scores.head(600)
    risk_fig = px.histogram(
        risk,
        x="denial_risk_score",
        color="risk_tier",
        nbins=32,
        color_discrete_sequence=["#22C55E", "#38BDF8", "#F59E0B", "#EF4444"],
        labels={"denial_risk_score": "Denial risk score"},
    )
    risk_fig.update_layout(height=360)

    return {
        "reason": _plot(reason_fig),
        "payer": _plot(payer_fig),
        "service": _plot(service_fig),
        "appeal": _plot(appeal_fig),
        "risk": _plot(risk_fig),
    }


def _plot(fig: go.Figure) -> str:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 18, "r": 18, "t": 26, "b": 34},
        font={"family": "Inter, Segoe UI, Arial, sans-serif", "size": 12, "color": "#DCE7F7"},
        legend={"orientation": "h", "y": -0.2, "font": {"color": "#A8B7CB"}},
        hoverlabel={
            "bgcolor": "rgba(12, 18, 31, 0.94)",
            "bordercolor": "rgba(148, 163, 184, 0.42)",
            "font": {"color": "#F8FAFC"},
        },
    )
    fig.update_xaxes(gridcolor="rgba(148, 163, 184, 0.16)", zerolinecolor="rgba(148, 163, 184, 0.22)")
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.12)", zerolinecolor="rgba(148, 163, 184, 0.22)")
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False, "responsive": True})


_DASHBOARD_TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Claims Denials Revenue Cycle Dashboard</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' x2='1' y1='0' y2='1'%3E%3Cstop stop-color='%2355C7FF'/%3E%3Cstop offset='.55' stop-color='%23A78BFA'/%3E%3Cstop offset='1' stop-color='%2334D399'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='64' height='64' rx='18' fill='url(%23g)'/%3E%3Cpath d='M18 34h8l5-13 7 24 5-11h5' fill='none' stroke='white' stroke-width='5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
  <script>
    const savedTheme = localStorage.getItem("claims-dashboard-theme");
    const preferredTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    document.documentElement.dataset.theme = savedTheme || preferredTheme;
  </script>
  <script>{{ plotly_js | safe }}</script>
  <style>
    :root {
      color-scheme: dark;
      --bg: #070A12;
      --bg-2: #0C1220;
      --surface: rgba(13, 20, 35, 0.68);
      --surface-strong: rgba(17, 25, 43, 0.84);
      --surface-soft: rgba(255, 255, 255, 0.055);
      --glass: rgba(255, 255, 255, 0.08);
      --glass-2: rgba(255, 255, 255, 0.12);
      --ink: #F8FAFC;
      --ink-soft: #DDE8F7;
      --muted: #9AA9BD;
      --line: rgba(204, 214, 232, 0.18);
      --line-strong: rgba(226, 232, 240, 0.34);
      --blue: #55C7FF;
      --cyan: #27E0D4;
      --violet: #A78BFA;
      --rose: #FB7185;
      --amber: #FBBF24;
      --green: #34D399;
      --red: #F87171;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
      --shadow-soft: 0 12px 40px rgba(2, 6, 23, 0.24);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --radius-md: 16px;
      --radius-sm: 12px;
      --focus: 0 0 0 3px rgba(85, 199, 255, 0.38);
    }

    :root[data-theme="light"] {
      color-scheme: light;
      --bg: #F5F8FC;
      --bg-2: #EAF1FA;
      --surface: rgba(255, 255, 255, 0.72);
      --surface-strong: rgba(255, 255, 255, 0.88);
      --surface-soft: rgba(8, 16, 30, 0.045);
      --glass: rgba(255, 255, 255, 0.66);
      --glass-2: rgba(255, 255, 255, 0.82);
      --ink: #101828;
      --ink-soft: #26344A;
      --muted: #64748B;
      --line: rgba(48, 64, 90, 0.14);
      --line-strong: rgba(48, 64, 90, 0.24);
      --blue: #0EA5E9;
      --cyan: #0D9488;
      --violet: #7C3AED;
      --rose: #E11D48;
      --amber: #B45309;
      --green: #047857;
      --red: #DC2626;
      --shadow: 0 28px 80px rgba(25, 38, 62, 0.16);
      --shadow-soft: 0 12px 36px rgba(25, 38, 62, 0.10);
    }

    * { box-sizing: border-box; }

    html {
      scroll-behavior: smooth;
      background: var(--bg);
    }

    body {
      margin: 0;
      color: var(--ink);
      min-height: 100vh;
      background:
        linear-gradient(135deg, rgba(85, 199, 255, 0.16), transparent 28%),
        linear-gradient(225deg, rgba(167, 139, 250, 0.14), transparent 30%),
        repeating-linear-gradient(90deg, rgba(148, 163, 184, 0.055) 0 1px, transparent 1px 72px),
        repeating-linear-gradient(0deg, rgba(148, 163, 184, 0.042) 0 1px, transparent 1px 72px),
        linear-gradient(180deg, var(--bg), var(--bg-2));
      font-family: Inter, ui-sans-serif, "Segoe UI", Arial, sans-serif;
      letter-spacing: 0;
      overflow-x: hidden;
    }

    body::before,
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
    }

    body::before {
      background:
        linear-gradient(115deg, transparent 0 28%, rgba(85, 199, 255, 0.08) 35%, transparent 43%),
        linear-gradient(68deg, transparent 0 55%, rgba(251, 113, 133, 0.06) 62%, transparent 72%);
      filter: blur(0.2px);
      animation: lightSweep 18s ease-in-out infinite alternate;
    }

    body::after {
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,0.95), transparent 78%);
    }

    a {
      color: inherit;
    }

    button,
    a {
      -webkit-tap-highlight-color: transparent;
    }

    button:focus-visible,
    a:focus-visible {
      outline: none;
      box-shadow: var(--focus);
    }

    .skip-link {
      position: fixed;
      left: 18px;
      top: 12px;
      z-index: 20;
      transform: translateY(-140%);
      border-radius: 999px;
      padding: 10px 14px;
      color: var(--ink);
      background: var(--surface-strong);
      border: 1px solid var(--line-strong);
      text-decoration: none;
      transition: transform 180ms ease;
    }

    .skip-link:focus {
      transform: translateY(0);
    }

    .particle-field {
      position: fixed;
      inset: 0;
      overflow: hidden;
      pointer-events: none;
      z-index: 0;
    }

    .particle-field span {
      position: absolute;
      width: 3px;
      height: 18px;
      border-radius: 999px;
      background: linear-gradient(180deg, transparent, rgba(85, 199, 255, 0.58), transparent);
      opacity: 0.34;
      animation: particleDrift 13s linear infinite;
    }

    .particle-field span:nth-child(1) { left: 8%; animation-delay: -1s; animation-duration: 14s; }
    .particle-field span:nth-child(2) { left: 17%; animation-delay: -7s; animation-duration: 18s; }
    .particle-field span:nth-child(3) { left: 27%; animation-delay: -4s; animation-duration: 15s; }
    .particle-field span:nth-child(4) { left: 41%; animation-delay: -10s; animation-duration: 20s; }
    .particle-field span:nth-child(5) { left: 56%; animation-delay: -3s; animation-duration: 17s; }
    .particle-field span:nth-child(6) { left: 63%; animation-delay: -12s; animation-duration: 19s; }
    .particle-field span:nth-child(7) { left: 74%; animation-delay: -6s; animation-duration: 16s; }
    .particle-field span:nth-child(8) { left: 86%; animation-delay: -9s; animation-duration: 21s; }

    .app-shell {
      position: relative;
      z-index: 1;
      max-width: 1540px;
      margin: 0 auto;
      padding: 18px;
    }

    .topbar {
      position: sticky;
      top: 14px;
      z-index: 10;
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 14px;
      min-height: 68px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background: linear-gradient(135deg, rgba(255,255,255,0.13), rgba(255,255,255,0.055));
      backdrop-filter: blur(28px) saturate(150%);
      box-shadow: var(--shadow-soft);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .brand-mark {
      position: relative;
      width: 42px;
      height: 42px;
      border-radius: 14px;
      background:
        linear-gradient(135deg, rgba(85, 199, 255, 0.96), rgba(167, 139, 250, 0.88) 52%, rgba(52, 211, 153, 0.84));
      box-shadow: 0 16px 36px rgba(85, 199, 255, 0.24);
      flex: 0 0 auto;
    }

    .brand-mark::before,
    .brand-mark::after {
      content: "";
      position: absolute;
      inset: 10px;
      border: 1px solid rgba(255, 255, 255, 0.78);
      border-radius: 9px;
      transform: rotate(8deg);
    }

    .brand-mark::after {
      inset: 15px;
      border-color: rgba(7, 10, 18, 0.42);
      transform: rotate(-12deg);
    }

    .brand-title {
      min-width: 0;
    }

    .brand-title strong {
      display: block;
      color: var(--ink);
      font-size: 0.96rem;
      line-height: 1.15;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .brand-title span {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 0.75rem;
    }

    .nav {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      min-width: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }

    .nav::-webkit-scrollbar {
      display: none;
    }

    .nav a,
    .control-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 0 14px;
      border: 1px solid transparent;
      border-radius: 999px;
      color: var(--ink-soft);
      background: transparent;
      font: inherit;
      font-size: 0.82rem;
      font-weight: 750;
      text-decoration: none;
      cursor: pointer;
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease, color 180ms ease;
      white-space: nowrap;
    }

    .nav a:hover,
    .control-button:hover {
      transform: translateY(-1px);
      border-color: var(--line-strong);
      background: var(--surface-soft);
      color: var(--ink);
    }

    .controls {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .control-button {
      background: linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.055));
      border-color: var(--line);
      min-width: 42px;
      padding: 0 12px;
    }

    .theme-toggle {
      width: 72px;
      position: relative;
      justify-content: flex-start;
      padding: 0 6px;
    }

    .theme-toggle::before {
      content: "";
      width: 30px;
      height: 30px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--blue), var(--violet));
      box-shadow: 0 8px 20px rgba(85, 199, 255, 0.30);
      transition: transform 220ms cubic-bezier(.2,.8,.2,1);
    }

    :root[data-theme="light"] .theme-toggle::before {
      transform: translateX(28px);
    }

    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 18px;
      align-items: stretch;
      margin-top: 18px;
    }

    .hero-copy {
      position: relative;
      overflow: hidden;
      min-height: 360px;
      padding: 34px;
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background:
        linear-gradient(135deg, rgba(255,255,255,0.15), rgba(255,255,255,0.05)),
        linear-gradient(120deg, rgba(85,199,255,0.16), transparent 32%, rgba(167,139,250,0.10) 68%, transparent);
      backdrop-filter: blur(30px) saturate(150%);
      box-shadow: var(--shadow);
    }

    .hero-copy::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent),
        repeating-linear-gradient(135deg, rgba(255,255,255,0.048) 0 1px, transparent 1px 18px);
      transform: translateX(-100%);
      animation: panelReflect 9s ease-in-out infinite;
      pointer-events: none;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--cyan);
      font-size: 0.78rem;
      font-weight: 850;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .eyebrow::before {
      content: "";
      width: 34px;
      height: 1px;
      background: linear-gradient(90deg, var(--cyan), transparent);
    }

    h1 {
      max-width: 940px;
      margin: 18px 0 14px;
      color: var(--ink);
      font-size: 3.1rem;
      line-height: 0.98;
      letter-spacing: 0;
      font-weight: 860;
    }

    .subtitle {
      max-width: 760px;
      margin: 0;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.7;
    }

    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 28px;
    }

    .primary-action,
    .secondary-action {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 46px;
      padding: 0 18px;
      border-radius: 999px;
      text-decoration: none;
      font-size: 0.88rem;
      font-weight: 820;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
    }

    .primary-action {
      color: #06101F;
      background: linear-gradient(135deg, #C8F7FF, #8FE4FF 46%, #D6C4FF);
      box-shadow: 0 18px 38px rgba(85, 199, 255, 0.23);
    }

    .secondary-action {
      color: var(--ink);
      border: 1px solid var(--line-strong);
      background: rgba(255,255,255,0.08);
      backdrop-filter: blur(14px);
    }

    .primary-action:hover,
    .secondary-action:hover {
      transform: translateY(-2px);
      box-shadow: 0 24px 44px rgba(85, 199, 255, 0.20);
    }

    .hero-side {
      display: grid;
      gap: 14px;
    }

    .insight-tile,
    .system-card,
    .kpi,
    .panel {
      position: relative;
      border: 1px solid var(--line);
      background:
        linear-gradient(135deg, rgba(255,255,255,0.14), rgba(255,255,255,0.055)),
        var(--surface);
      backdrop-filter: blur(26px) saturate(150%);
      box-shadow: var(--shadow-soft);
    }

    .insight-tile {
      overflow: hidden;
      min-height: 154px;
      padding: 22px;
      border-radius: var(--radius-xl);
    }

    .insight-tile::after {
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 2px;
      background: linear-gradient(90deg, var(--blue), var(--cyan), var(--violet), var(--rose));
      opacity: 0.9;
    }

    .tile-label,
    .panel-label {
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 820;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .tile-value {
      margin-top: 16px;
      color: var(--ink);
      font-size: 2.05rem;
      font-weight: 860;
      line-height: 1;
    }

    .tile-copy {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.86rem;
      line-height: 1.55;
    }

    .system-card {
      display: grid;
      gap: 14px;
      padding: 22px;
      border-radius: var(--radius-xl);
    }

    .system-row {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 12px;
      color: var(--ink-soft);
      font-size: 0.9rem;
    }

    .system-row span:last-child {
      color: var(--green);
      font-weight: 850;
    }

    main {
      padding: 18px 0 44px;
    }

    .section-heading {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 18px;
      margin: 26px 0 14px;
    }

    .section-heading h2 {
      margin: 0;
      color: var(--ink);
      font-size: 1.26rem;
      letter-spacing: 0;
    }

    .section-heading p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.88rem;
    }

    .kpis {
      display: grid;
      grid-template-columns: repeat(5, minmax(170px, 1fr));
      gap: 14px;
    }

    .kpi {
      overflow: hidden;
      min-height: 132px;
      padding: 18px;
      border-radius: var(--radius-lg);
      transition: transform 220ms ease, border-color 220ms ease, box-shadow 220ms ease;
    }

    .kpi::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      padding: 1px;
      background: linear-gradient(135deg, rgba(85,199,255,0.72), rgba(167,139,250,0.18), rgba(52,211,153,0.45));
      mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      mask-composite: exclude;
      opacity: 0;
      transition: opacity 220ms ease;
      pointer-events: none;
    }

    .kpi:hover {
      transform: translateY(-4px);
      border-color: var(--line-strong);
      box-shadow: var(--shadow);
    }

    .kpi:hover::before {
      opacity: 1;
    }

    .kpi span {
      display: block;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 840;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .kpi strong {
      display: block;
      margin-top: 15px;
      color: var(--ink);
      font-size: 1.72rem;
      line-height: 1;
      font-weight: 880;
      font-variant-numeric: tabular-nums;
    }

    .kpi em {
      display: block;
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.78rem;
      font-style: normal;
      line-height: 1.45;
    }

    .kpi[data-tone="blue"] { --tone: var(--blue); }
    .kpi[data-tone="cyan"] { --tone: var(--cyan); }
    .kpi[data-tone="violet"] { --tone: var(--violet); }
    .kpi[data-tone="rose"] { --tone: var(--rose); }
    .kpi[data-tone="green"] { --tone: var(--green); }
    .kpi[data-tone="amber"] { --tone: var(--amber); }
    .kpi::after {
      content: "";
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: 0;
      height: 3px;
      border-radius: 999px 999px 0 0;
      background: linear-gradient(90deg, var(--tone, var(--blue)), transparent);
      opacity: 0.82;
    }

    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-top: 16px;
    }

    .panel {
      border-radius: var(--radius-xl);
      overflow: hidden;
      min-height: 360px;
      transition: transform 220ms ease, border-color 220ms ease, box-shadow 220ms ease;
    }

    .panel:hover {
      transform: translateY(-3px);
      border-color: var(--line-strong);
      box-shadow: var(--shadow);
    }

    .panel.wide {
      grid-column: 1 / -1;
    }

    .panel-header {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 20px 8px;
    }

    .panel h2 {
      margin: 4px 0 0;
      color: var(--ink);
      font-size: 1.02rem;
      line-height: 1.3;
      letter-spacing: 0;
    }

    .panel-subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.45;
    }

    .panel-action {
      flex: 0 0 auto;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0 12px;
      color: var(--ink-soft);
      background: rgba(255,255,255,0.06);
      font-size: 0.75rem;
      font-weight: 800;
    }

    .chart-frame {
      padding: 0 8px 10px;
    }

    .table-shell {
      margin: 10px 14px 16px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: rgba(255,255,255,0.035);
      max-height: 520px;
    }

    .tool-panel {
      display: grid;
      gap: 12px;
      margin: 10px 14px 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      background: rgba(255, 255, 255, 0.045);
    }

    .filter-grid {
      display: grid;
      grid-template-columns: minmax(220px, 1.4fr) repeat(3, minmax(150px, 1fr)) auto;
      gap: 10px;
      align-items: end;
    }

    .field {
      display: grid;
      gap: 6px;
    }

    .field label {
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 840;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .field input,
    .field select {
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 0 12px;
      color: var(--ink);
      background: color-mix(in srgb, var(--surface-strong) 82%, transparent);
      font: inherit;
      font-size: 0.86rem;
      outline: none;
      transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
    }

    .field input:focus,
    .field select:focus {
      border-color: color-mix(in srgb, var(--blue) 72%, var(--line));
      box-shadow: var(--focus);
    }

    .action-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 0.82rem;
    }

    .button-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .mini-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0 12px;
      color: var(--ink-soft);
      background: rgba(255,255,255,0.06);
      font: inherit;
      font-size: 0.76rem;
      font-weight: 820;
      cursor: pointer;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }

    .mini-button:hover {
      transform: translateY(-1px);
      border-color: var(--line-strong);
      background: rgba(85, 199, 255, 0.10);
    }

    .mini-button[data-state="active"] {
      color: #06101F;
      border-color: transparent;
      background: linear-gradient(135deg, #BFF3FF, #D6C4FF);
    }

    th[data-sort],
    th[data-sort-underpay] {
      cursor: pointer;
      user-select: none;
    }

    th[data-sort]::after,
    th[data-sort-underpay]::after {
      content: "sort";
      margin-left: 6px;
      color: var(--muted);
      font-size: 0.68rem;
    }

    tr[data-status="resolved"] td {
      color: color-mix(in srgb, var(--muted) 76%, transparent);
      text-decoration: line-through;
    }

    .row-actions {
      display: inline-flex;
      gap: 6px;
      white-space: nowrap;
    }

    .empty-row td {
      padding: 28px;
      color: var(--muted);
      text-align: center;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
      font-size: 0.78rem;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      text-align: left;
      color: var(--ink-soft);
      background: color-mix(in srgb, var(--surface-strong) 86%, transparent);
      backdrop-filter: blur(18px);
      font-size: 0.72rem;
      font-weight: 850;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    th, td {
      padding: 12px 13px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }

    td {
      color: var(--ink-soft);
      line-height: 1.45;
    }

    tbody tr {
      transition: background 160ms ease;
    }

    tbody tr:hover {
      background: rgba(85, 199, 255, 0.07);
    }

    tr:last-child td {
      border-bottom: 0;
    }

    .status-PASS,
    .status-WARN,
    .status-FAIL {
      font-weight: 880;
      letter-spacing: 0.04em;
    }

    .status-PASS { color: var(--green); }
    .status-WARN { color: var(--amber); }
    .status-FAIL { color: var(--red); }

    .money, .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 30;
      display: grid;
      place-items: center;
      padding: 20px;
      background: rgba(0, 0, 0, 0.52);
      backdrop-filter: blur(18px);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease;
    }

    .modal-backdrop[aria-hidden="false"] {
      opacity: 1;
      pointer-events: auto;
    }

    .modal {
      width: min(620px, 100%);
      border: 1px solid var(--line-strong);
      border-radius: var(--radius-xl);
      background: var(--surface-strong);
      box-shadow: var(--shadow);
      transform: translateY(14px) scale(0.98);
      transition: transform 180ms ease;
    }

    .modal-backdrop[aria-hidden="false"] .modal {
      transform: translateY(0) scale(1);
    }

    .modal-header,
    .modal-body {
      padding: 20px;
    }

    .modal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
    }

    .modal-header h2 {
      margin: 0;
      font-size: 1.1rem;
    }

    .modal-body p {
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }

    .detail-list {
      display: grid;
      gap: 10px;
      margin: 0;
    }

    .detail-list div {
      display: grid;
      grid-template-columns: 170px 1fr;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
    }

    .detail-list div:last-child {
      border-bottom: 0;
    }

    .detail-list dt {
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 840;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .detail-list dd {
      margin: 0;
      color: var(--ink-soft);
    }

    .loading-screen {
      position: fixed;
      inset: 0;
      z-index: 50;
      display: grid;
      place-items: center;
      background: var(--bg);
      transition: opacity 340ms ease, visibility 340ms ease;
    }

    .loader-card {
      width: min(360px, calc(100vw - 42px));
      padding: 20px;
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background: var(--surface);
      backdrop-filter: blur(24px);
      box-shadow: var(--shadow);
    }

    .skeleton-line {
      height: 12px;
      margin: 12px 0;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(255,255,255,0.06), rgba(255,255,255,0.22), rgba(255,255,255,0.06));
      background-size: 220% 100%;
      animation: skeleton 1.25s ease-in-out infinite;
    }

    .skeleton-line:nth-child(2) { width: 72%; }
    .skeleton-line:nth-child(3) { width: 88%; }
    .skeleton-line:nth-child(4) { width: 56%; }

    body.is-ready .loading-screen {
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
    }

    @keyframes skeleton {
      0% { background-position: 100% 0; }
      100% { background-position: -100% 0; }
    }

    @keyframes lightSweep {
      from { transform: translate3d(-2%, -1%, 0); opacity: 0.76; }
      to { transform: translate3d(2%, 1%, 0); opacity: 1; }
    }

    @keyframes particleDrift {
      from { transform: translate3d(0, 110vh, 0); }
      to { transform: translate3d(0, -20vh, 0); }
    }

    @keyframes panelReflect {
      0%, 42% { transform: translateX(-115%); opacity: 0; }
      55% { opacity: 1; }
      70%, 100% { transform: translateX(115%); opacity: 0; }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.001ms !important;
      }
    }

    @media (max-width: 980px) {
      .app-shell {
        padding: 12px;
      }

      .topbar {
        grid-template-columns: 1fr auto;
      }

      .nav {
        grid-column: 1 / -1;
        justify-content: flex-start;
        order: 3;
      }

      .hero,
      .kpis,
      .grid,
      .filter-grid {
        grid-template-columns: 1fr;
      }

      .hero-copy {
        min-height: auto;
        padding: 26px;
      }

      h1 {
        font-size: 2.2rem;
      }

      table {
        font-size: 0.74rem;
      }
    }

    @media (max-width: 640px) {
      .brand-title strong {
        white-space: normal;
      }

      .controls {
        align-self: start;
      }

      .hero-copy,
      .insight-tile,
      .system-card {
        border-radius: 20px;
      }

      h1 {
        font-size: 1.92rem;
      }

      .hero-actions {
        display: grid;
      }

      .primary-action,
      .secondary-action {
        width: 100%;
      }

      .section-heading {
        align-items: start;
        flex-direction: column;
      }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to dashboard</a>
  <div class="loading-screen" aria-hidden="true">
    <div class="loader-card">
      <div class="skeleton-line"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line"></div>
    </div>
  </div>
  <div class="particle-field" aria-hidden="true">
    <span></span><span></span><span></span><span></span>
    <span></span><span></span><span></span><span></span>
  </div>

  <div class="app-shell">
    <header class="topbar">
      <div class="brand" aria-label="Claims Denials dashboard">
        <div class="brand-mark" aria-hidden="true"></div>
        <div class="brand-title">
          <strong>Claims Denials Intelligence</strong>
          <span>Revenue cycle command center</span>
        </div>
      </div>
      <nav class="nav" aria-label="Dashboard sections">
        <a href="#overview">Overview</a>
        <a href="#analytics">Analytics</a>
        <a href="#queue">Work Queue</a>
        <a href="#quality">Quality</a>
      </nav>
      <div class="controls">
        <button class="control-button" type="button" data-modal-open aria-haspopup="dialog">Governance</button>
        <button class="control-button theme-toggle" type="button" aria-label="Toggle color theme" data-theme-toggle></button>
      </div>
    </header>

    <section class="hero" id="overview">
      <div class="hero-copy">
        <div class="eyebrow">Enterprise analytics platform</div>
        <h1>Claims Denials, Appeals & Revenue Cycle Intelligence</h1>
        <p class="subtitle">Simulated claim-level adjudication, appeal prioritization, payer friction, revenue leakage, underpayment opportunity, and operational data-quality monitoring.</p>
        <div class="hero-actions">
          <a class="primary-action" href="#queue">Open Work Queue</a>
          <a class="secondary-action" href="#analytics">Review Analytics</a>
        </div>
      </div>
      <aside class="hero-side" aria-label="Platform status">
        <div class="insight-tile">
          <div class="tile-label">Expected Recovery Value</div>
          <div class="tile-value">${{ "{:,.0f}".format(kpis.expected_recovery_value) }}</div>
          <div class="tile-copy">Ranked by recoverability, appeal probability, preventability, and operational priority.</div>
        </div>
        <div class="system-card">
          <div class="system-row"><span>Quality gate</span><span>{{ quality | selectattr("status", "equalto", "FAIL") | list | length }} failures</span></div>
          <div class="system-row"><span>Model scores</span><span>Active</span></div>
          <div class="system-row"><span>Open queue</span><span>{{ "{:,}".format(kpis.open_work_queue) }}</span></div>
        </div>
      </aside>
    </section>

    <main id="main">
      <div class="section-heading">
        <div>
          <div class="panel-label">Operating snapshot</div>
          <h2>Revenue Cycle Performance</h2>
          <p>Denial, appeal, recovery, underpayment, and quality signals.</p>
        </div>
      </div>

      <section class="kpis" aria-label="Key performance indicators">
        <div class="kpi" data-tone="blue"><span>Claims Received</span><strong>{{ "{:,}".format(kpis.claims_received) }}</strong><em>Submitted claim volume</em></div>
        <div class="kpi" data-tone="rose"><span>Denied Claims</span><strong>{{ "{:,}".format(kpis.denied_claims) }}</strong><em>Claims requiring follow-up</em></div>
        <div class="kpi" data-tone="violet"><span>Denial Rate</span><strong>{{ "{:.1%}".format(kpis.denial_rate) }}</strong><em>Denied claims over received</em></div>
        <div class="kpi" data-tone="cyan"><span>Denied Amount</span><strong>${{ "{:,.0f}".format(kpis.denied_amount) }}</strong><em>Total revenue at risk</em></div>
        <div class="kpi" data-tone="green"><span>Expected Recovery</span><strong>${{ "{:,.0f}".format(kpis.expected_recovery_value) }}</strong><em>Modeled recovery value</em></div>
        <div class="kpi" data-tone="green"><span>Appeal Success</span><strong>{{ "{:.1%}".format(kpis.appeal_success_rate) }}</strong><em>Overturned or partial wins</em></div>
        <div class="kpi" data-tone="cyan"><span>Recovered Amount</span><strong>${{ "{:,.0f}".format(kpis.recovered_amount) }}</strong><em>Appeal dollars recovered</em></div>
        <div class="kpi" data-tone="amber"><span>Underpayment</span><strong>${{ "{:,.0f}".format(kpis.underpaid_amount) }}</strong><em>Contract review exposure</em></div>
        <div class="kpi" data-tone="blue"><span>Work Queue</span><strong>{{ "{:,}".format(kpis.open_work_queue) }}</strong><em>Open actionable items</em></div>
        <div class="kpi" data-tone="green"><span>Quality Failures</span><strong>{{ quality | selectattr("status", "equalto", "FAIL") | list | length }}</strong><em>Pipeline validation status</em></div>
      </section>

      <div class="section-heading" id="analytics">
        <div>
          <div class="panel-label">Analytics studio</div>
          <h2>Signals, Drivers, and Opportunity</h2>
          <p>Interactive charts are embedded with the standalone dashboard.</p>
        </div>
      </div>

      <section class="grid">
        <article class="panel">
          <div class="panel-header"><div><div class="panel-label">Root cause</div><h2>Denial Reason Pareto</h2><div class="panel-subtitle">Denied amount concentration by denial category.</div></div></div>
          <div class="chart-frame">{{ figures.reason | safe }}</div>
        </article>
        <article class="panel">
          <div class="panel-header"><div><div class="panel-label">Payer strategy</div><h2>Payer Friction Matrix</h2><div class="panel-subtitle">Denial rate, upheld rate, and dollar exposure.</div></div></div>
          <div class="chart-frame">{{ figures.payer | safe }}</div>
        </article>
        <article class="panel">
          <div class="panel-header"><div><div class="panel-label">Recovery</div><h2>Service-Line Recovery Opportunity</h2><div class="panel-subtitle">Expected recovery value by operational service line.</div></div></div>
          <div class="chart-frame">{{ figures.service | safe }}</div>
        </article>
        <article class="panel">
          <div class="panel-header"><div><div class="panel-label">Appeals</div><h2>Appeal Outcome Mix</h2><div class="panel-subtitle">Closed and pending appeal distribution.</div></div></div>
          <div class="chart-frame">{{ figures.appeal | safe }}</div>
        </article>
        <article class="panel wide">
          <div class="panel-header"><div><div class="panel-label">Predictive model</div><h2>Denial Risk Score Distribution</h2><div class="panel-subtitle">Pre-bill risk tiers generated by the scoring model.</div></div></div>
          <div class="chart-frame">{{ figures.risk | safe }}</div>
        </article>

        <article class="panel wide" id="queue">
          <div class="panel-header">
            <div><div class="panel-label">Operations</div><h2>Priority Denial Work Queue</h2><div class="panel-subtitle">Open denials ranked by recovery value and operational urgency.</div></div>
          </div>
          <div class="tool-panel" aria-label="Work queue controls">
            <div class="filter-grid">
              <div class="field">
                <label for="queue-search">Search queue</label>
                <input id="queue-search" data-queue-search type="search" placeholder="Claim, payer, reason, action">
              </div>
              <div class="field">
                <label for="queue-payer">Payer</label>
                <select id="queue-payer" data-queue-filter="issuer_name"></select>
              </div>
              <div class="field">
                <label for="queue-service">Service line</label>
                <select id="queue-service" data-queue-filter="service_line"></select>
              </div>
              <div class="field">
                <label for="queue-reason">Reason</label>
                <select id="queue-reason" data-queue-filter="denial_reason_category"></select>
              </div>
              <button class="mini-button" type="button" data-queue-clear>Reset</button>
            </div>
            <div class="action-row">
              <span data-queue-count>Loading queue...</span>
              <div class="button-row">
                <button class="mini-button" type="button" data-queue-view="open" data-state="active">Open</button>
                <button class="mini-button" type="button" data-queue-view="flagged">Flagged</button>
                <button class="mini-button" type="button" data-queue-view="resolved">Resolved</button>
                <button class="mini-button" type="button" data-queue-export>Export CSV</button>
              </div>
            </div>
          </div>
          <div class="table-shell">
            <table data-table="queue">
              <thead>
                <tr>
                  <th data-sort="claim_id">Claim</th><th data-sort="issuer_name">Payer</th><th data-sort="service_line">Service Line</th><th data-sort="denial_reason_category">Reason</th><th class="money" data-sort="denied_amount">Denied</th><th class="money" data-sort="expected_recovery_value">Expected Recovery</th><th class="num" data-sort="priority_score">Priority</th><th>Action</th><th>Triage</th>
                </tr>
              </thead>
              <tbody data-queue-body><tr class="empty-row"><td colspan="9">Loading work queue...</td></tr></tbody>
            </table>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header"><div><div class="panel-label">Contracting</div><h2>Underpayment Opportunities</h2><div class="panel-subtitle">Claims with paid amount below expected or matched contract rate.</div></div></div>
          <div class="tool-panel" aria-label="Underpayment controls">
            <div class="filter-grid">
              <div class="field">
                <label for="underpay-search">Search</label>
                <input id="underpay-search" data-underpay-search type="search" placeholder="Claim, payer, service">
              </div>
              <div class="field">
                <label for="underpay-payer">Payer</label>
                <select id="underpay-payer" data-underpay-filter="issuer_name"></select>
              </div>
              <div class="field">
                <label for="underpay-service">Service</label>
                <select id="underpay-service" data-underpay-filter="service_line"></select>
              </div>
              <button class="mini-button" type="button" data-underpay-clear>Reset</button>
              <button class="mini-button" type="button" data-underpay-export>Export</button>
            </div>
            <div class="action-row"><span data-underpay-count>Loading opportunities...</span></div>
          </div>
          <div class="table-shell">
            <table data-table="underpayment">
              <thead>
                <tr><th data-sort-underpay="claim_id">Claim</th><th data-sort-underpay="issuer_name">Payer</th><th data-sort-underpay="service_line">Service</th><th class="money" data-sort-underpay="underpaid_amount">Underpaid</th><th>Review</th></tr>
              </thead>
              <tbody data-underpay-body><tr class="empty-row"><td colspan="5">Loading underpayment opportunities...</td></tr></tbody>
            </table>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header"><div><div class="panel-label">ML explainability</div><h2>Top Model Drivers</h2><div class="panel-subtitle">Highest feature importance values across scoring models.</div></div></div>
          <div class="table-shell">
            <table>
              <thead><tr><th>Model</th><th>Feature</th><th class="num">Importance</th></tr></thead>
              <tbody>
              {% for row in top_features %}
                <tr>
                  <td>{{ row.model_name }}</td>
                  <td>{{ row.feature }}</td>
                  <td class="num">{{ "{:.3f}".format(row.importance) }}</td>
                </tr>
              {% endfor %}
              </tbody>
            </table>
          </div>
        </article>

        <article class="panel wide" id="quality">
          <div class="panel-header"><div><div class="panel-label">Governance</div><h2>Data Quality Gate</h2><div class="panel-subtitle">Automated validation for benchmark, simulation, mart, and model outputs.</div></div></div>
          <div class="table-shell">
            <table>
              <thead><tr><th>Status</th><th>Check</th><th>Detail</th></tr></thead>
              <tbody>
              {% for row in quality %}
                <tr>
                  <td class="status-{{ row.status }}">{{ row.status }}</td>
                  <td>{{ row.check_name }}</td>
                  <td>{{ row.detail }}</td>
                </tr>
              {% endfor %}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  </div>

  <div class="modal-backdrop" aria-hidden="true" data-modal>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="governance-title">
      <div class="modal-header">
        <h2 id="governance-title" data-modal-title>Simulation Governance</h2>
        <button class="control-button" type="button" data-modal-close aria-label="Close governance dialog">Close</button>
      </div>
      <div class="modal-body" data-modal-body>
        <p>Claim-level denial events are simulated from synthetic claims using transparent business rules and calibrated against public benchmark-style aggregate denial rates. They are not real patient, provider, or payer adjudication records.</p>
      </div>
    </section>
  </div>

  <script>
    const root = document.documentElement;
    const themeButton = document.querySelector("[data-theme-toggle]");
    const modal = document.querySelector("[data-modal]");
    const modalOpen = document.querySelector("[data-modal-open]");
    const modalClose = document.querySelector("[data-modal-close]");
    const modalTitle = document.querySelector("[data-modal-title]");
    const modalBody = document.querySelector("[data-modal-body]");
    const workQueueRows = {{ work_queue_json | safe }};
    const underpaymentRows = {{ underpayment_json | safe }};
    const moneyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
    const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
    const queueStoreKey = "claims-dashboard-queue-state";
    let lastModalFocus = modalOpen;
    let queueView = "open";
    let queueSort = { key: "priority_score", direction: "desc" };
    let underpaySort = { key: "underpaid_amount", direction: "desc" };
    let lastQueueRows = [];
    let lastUnderpayRows = [];

    function readQueueState() {
      try {
        return JSON.parse(localStorage.getItem(queueStoreKey) || "{}");
      } catch {
        return {};
      }
    }

    function writeQueueState(state) {
      localStorage.setItem(queueStoreKey, JSON.stringify(state));
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function asMoney(value) {
      return moneyFormatter.format(Number(value || 0));
    }

    function asNumber(value) {
      return numberFormatter.format(Number(value || 0));
    }

    function rowKey(row) {
      return row.claim_id || row.denial_key || JSON.stringify(row);
    }

    function populateSelect(select, rows, key, label) {
      if (!select) return;
      const current = select.value;
      const values = Array.from(new Set(rows.map((row) => row[key]).filter(Boolean))).sort();
      select.innerHTML = `<option value="">All ${label}</option>` + values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
      select.value = values.includes(current) ? current : "";
    }

    function sortRows(rows, sortState) {
      const direction = sortState.direction === "asc" ? 1 : -1;
      return [...rows].sort((left, right) => {
        const a = left[sortState.key];
        const b = right[sortState.key];
        const aNum = Number(a);
        const bNum = Number(b);
        if (Number.isFinite(aNum) && Number.isFinite(bNum)) return (aNum - bNum) * direction;
        return String(a ?? "").localeCompare(String(b ?? "")) * direction;
      });
    }

    function downloadCsv(filename, rows) {
      if (!rows.length) return;
      const columns = Object.keys(rows[0]).filter((column) => !column.startsWith("_"));
      const csv = [
        columns.join(","),
        ...rows.map((row) => columns.map((column) => `"${String(row[column] ?? "").replaceAll('"', '""')}"`).join(",")),
      ].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function applyQueueFilters() {
      const state = readQueueState();
      const query = document.querySelector("[data-queue-search]")?.value.trim().toLowerCase() || "";
      const filters = Array.from(document.querySelectorAll("[data-queue-filter]")).map((select) => [select.dataset.queueFilter, select.value]).filter(([, value]) => value);
      let rows = workQueueRows.map((row) => {
        const triage = state[rowKey(row)] || {};
        return { ...row, _resolved: Boolean(triage.resolved), _flagged: Boolean(triage.flagged) };
      });
      if (query) {
        rows = rows.filter((row) => [
          row.claim_id,
          row.issuer_name,
          row.plan_name,
          row.service_line,
          row.denial_reason_category,
          row.recommended_action,
        ].some((value) => String(value ?? "").toLowerCase().includes(query)));
      }
      filters.forEach(([key, value]) => {
        rows = rows.filter((row) => String(row[key]) === value);
      });
      if (queueView === "open") rows = rows.filter((row) => !row._resolved);
      if (queueView === "flagged") rows = rows.filter((row) => row._flagged && !row._resolved);
      if (queueView === "resolved") rows = rows.filter((row) => row._resolved);
      lastQueueRows = sortRows(rows, queueSort);
      renderQueue();
    }

    function renderQueue() {
      const body = document.querySelector("[data-queue-body]");
      const count = document.querySelector("[data-queue-count]");
      if (!body) return;
      const visibleRows = lastQueueRows.slice(0, 100);
      count.textContent = `${asNumber(lastQueueRows.length)} matching denials shown from ${asNumber(workQueueRows.length)} exportable rows`;
      if (!visibleRows.length) {
        body.innerHTML = `<tr class="empty-row"><td colspan="9">No denials match the current filters.</td></tr>`;
        return;
      }
      body.innerHTML = visibleRows.map((row) => {
        const key = escapeHtml(rowKey(row));
        return `
          <tr data-key="${key}" data-status="${row._resolved ? "resolved" : "open"}">
            <td>${escapeHtml(row.claim_id)}</td>
            <td>${escapeHtml(row.issuer_name)}</td>
            <td>${escapeHtml(row.service_line)}</td>
            <td>${escapeHtml(row.denial_reason_category)}</td>
            <td class="money">${asMoney(row.denied_amount)}</td>
            <td class="money">${asMoney(row.expected_recovery_value)}</td>
            <td class="num">${asNumber(row.priority_score)}</td>
            <td>${escapeHtml(row.recommended_action)}</td>
            <td>
              <span class="row-actions">
                <button class="mini-button" type="button" data-row-detail="${key}">Details</button>
                <button class="mini-button" type="button" data-row-flag="${key}" data-state="${row._flagged ? "active" : ""}">Flag</button>
                <button class="mini-button" type="button" data-row-resolve="${key}" data-state="${row._resolved ? "active" : ""}">${row._resolved ? "Reopen" : "Resolve"}</button>
              </span>
            </td>
          </tr>
        `;
      }).join("");
    }

    function queueRowByKey(key) {
      return workQueueRows.find((row) => rowKey(row) === key);
    }

    function toggleQueueState(key, field) {
      const state = readQueueState();
      state[key] = { ...(state[key] || {}), [field]: !state[key]?.[field] };
      writeQueueState(state);
      applyQueueFilters();
    }

    function openQueueDetails(key, source) {
      const row = queueRowByKey(key);
      if (!row) return;
      openModal({
        title: `Claim ${escapeHtml(row.claim_id)}`,
        body: `
          <dl class="detail-list">
            <div><dt>Payer</dt><dd>${escapeHtml(row.issuer_name)}</dd></div>
            <div><dt>Plan</dt><dd>${escapeHtml(row.plan_name)}</dd></div>
            <div><dt>Service line</dt><dd>${escapeHtml(row.service_line)}</dd></div>
            <div><dt>Denial reason</dt><dd>${escapeHtml(row.denial_reason_category)}</dd></div>
            <div><dt>Denied amount</dt><dd>${asMoney(row.denied_amount)}</dd></div>
            <div><dt>Expected recovery</dt><dd>${asMoney(row.expected_recovery_value)}</dd></div>
            <div><dt>Recommended action</dt><dd>${escapeHtml(row.recommended_action)}</dd></div>
          </dl>
        `,
        source,
      });
    }

    function applyUnderpaymentFilters() {
      const query = document.querySelector("[data-underpay-search]")?.value.trim().toLowerCase() || "";
      const filters = Array.from(document.querySelectorAll("[data-underpay-filter]")).map((select) => [select.dataset.underpayFilter, select.value]).filter(([, value]) => value);
      let rows = [...underpaymentRows];
      if (query) {
        rows = rows.filter((row) => [row.claim_id, row.issuer_name, row.service_line, row.provider_name].some((value) => String(value ?? "").toLowerCase().includes(query)));
      }
      filters.forEach(([key, value]) => {
        rows = rows.filter((row) => String(row[key]) === value);
      });
      lastUnderpayRows = sortRows(rows, underpaySort);
      renderUnderpayments();
    }

    function renderUnderpayments() {
      const body = document.querySelector("[data-underpay-body]");
      const count = document.querySelector("[data-underpay-count]");
      if (!body) return;
      const visibleRows = lastUnderpayRows.slice(0, 100);
      count.textContent = `${asNumber(lastUnderpayRows.length)} matching opportunities shown from ${asNumber(underpaymentRows.length)} exportable rows`;
      if (!visibleRows.length) {
        body.innerHTML = `<tr class="empty-row"><td colspan="5">No underpayment opportunities match the current filters.</td></tr>`;
        return;
      }
      body.innerHTML = visibleRows.map((row) => `
        <tr>
          <td>${escapeHtml(row.claim_id)}</td>
          <td>${escapeHtml(row.issuer_name)}</td>
          <td>${escapeHtml(row.service_line)}</td>
          <td class="money">${asMoney(row.underpaid_amount)}</td>
          <td>${row.contract_review_flag ? "Yes" : "No"}</td>
        </tr>
      `).join("");
    }

    function initializeInteractiveTables() {
      populateSelect(document.querySelector('[data-queue-filter="issuer_name"]'), workQueueRows, "issuer_name", "payers");
      populateSelect(document.querySelector('[data-queue-filter="service_line"]'), workQueueRows, "service_line", "service lines");
      populateSelect(document.querySelector('[data-queue-filter="denial_reason_category"]'), workQueueRows, "denial_reason_category", "reasons");
      populateSelect(document.querySelector('[data-underpay-filter="issuer_name"]'), underpaymentRows, "issuer_name", "payers");
      populateSelect(document.querySelector('[data-underpay-filter="service_line"]'), underpaymentRows, "service_line", "services");
      applyQueueFilters();
      applyUnderpaymentFilters();
    }

    function updatePlotTheme() {
      const isLight = root.dataset.theme === "light";
      const fontColor = isLight ? "#26344A" : "#DCE7F7";
      const gridColor = isLight ? "rgba(48, 64, 90, 0.14)" : "rgba(148, 163, 184, 0.16)";
      document.querySelectorAll(".plotly-graph-div").forEach((plot) => {
        if (!window.Plotly || !plot.data) return;
        window.Plotly.relayout(plot, {
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          "font.color": fontColor,
          "xaxis.gridcolor": gridColor,
          "yaxis.gridcolor": gridColor,
          "legend.font.color": fontColor
        });
      });
    }

    function setTheme(theme) {
      root.dataset.theme = theme;
      localStorage.setItem("claims-dashboard-theme", theme);
      requestAnimationFrame(updatePlotTheme);
    }

    themeButton?.addEventListener("click", () => {
      setTheme(root.dataset.theme === "light" ? "dark" : "light");
    });

    function openModal(options = {}) {
      lastModalFocus = options.source || document.activeElement || modalOpen;
      if (modalTitle && options.title) modalTitle.textContent = options.title;
      if (modalBody && options.body) modalBody.innerHTML = options.body;
      modal?.setAttribute("aria-hidden", "false");
      modalClose?.focus();
    }

    function closeModal() {
      modal?.setAttribute("aria-hidden", "true");
      lastModalFocus?.focus?.();
    }

    modalOpen?.addEventListener("click", (event) => {
      openModal({
        source: event.currentTarget,
        title: "Simulation Governance",
        body: "<p>Claim-level denial events are simulated from synthetic claims using transparent business rules and calibrated against public benchmark-style aggregate denial rates. They are not real patient, provider, or payer adjudication records.</p>",
      });
    });
    modalClose?.addEventListener("click", closeModal);
    modal?.addEventListener("click", (event) => {
      if (event.target === modal) closeModal();
    });
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && modal?.getAttribute("aria-hidden") === "false") {
        closeModal();
      }
    });

    document.querySelector("[data-queue-search]")?.addEventListener("input", applyQueueFilters);
    document.querySelectorAll("[data-queue-filter]").forEach((select) => select.addEventListener("change", applyQueueFilters));
    document.querySelector("[data-queue-clear]")?.addEventListener("click", () => {
      document.querySelector("[data-queue-search]").value = "";
      document.querySelectorAll("[data-queue-filter]").forEach((select) => { select.value = ""; });
      applyQueueFilters();
    });
    document.querySelector("[data-queue-export]")?.addEventListener("click", () => downloadCsv("denial_work_queue_filtered.csv", lastQueueRows));
    document.querySelectorAll("[data-queue-view]").forEach((button) => {
      button.addEventListener("click", () => {
        queueView = button.dataset.queueView;
        document.querySelectorAll("[data-queue-view]").forEach((item) => item.dataset.state = item === button ? "active" : "");
        applyQueueFilters();
      });
    });
    document.querySelectorAll("[data-sort]").forEach((header) => {
      header.addEventListener("click", () => {
        const key = header.dataset.sort;
        queueSort = { key, direction: queueSort.key === key && queueSort.direction === "desc" ? "asc" : "desc" };
        applyQueueFilters();
      });
    });
    document.querySelector("[data-queue-body]")?.addEventListener("click", (event) => {
      const detail = event.target.closest("[data-row-detail]");
      const flag = event.target.closest("[data-row-flag]");
      const resolve = event.target.closest("[data-row-resolve]");
      if (detail) openQueueDetails(detail.dataset.rowDetail, detail);
      if (flag) toggleQueueState(flag.dataset.rowFlag, "flagged");
      if (resolve) toggleQueueState(resolve.dataset.rowResolve, "resolved");
    });

    document.querySelector("[data-underpay-search]")?.addEventListener("input", applyUnderpaymentFilters);
    document.querySelectorAll("[data-underpay-filter]").forEach((select) => select.addEventListener("change", applyUnderpaymentFilters));
    document.querySelector("[data-underpay-clear]")?.addEventListener("click", () => {
      document.querySelector("[data-underpay-search]").value = "";
      document.querySelectorAll("[data-underpay-filter]").forEach((select) => { select.value = ""; });
      applyUnderpaymentFilters();
    });
    document.querySelector("[data-underpay-export]")?.addEventListener("click", () => downloadCsv("underpayment_opportunities_filtered.csv", lastUnderpayRows));
    document.querySelectorAll("[data-sort-underpay]").forEach((header) => {
      header.addEventListener("click", () => {
        const key = header.dataset.sortUnderpay;
        underpaySort = { key, direction: underpaySort.key === key && underpaySort.direction === "desc" ? "asc" : "desc" };
        applyUnderpaymentFilters();
      });
    });

    window.addEventListener("load", () => {
      document.body.classList.add("is-ready");
      initializeInteractiveTables();
      updatePlotTheme();
      setTimeout(() => window.dispatchEvent(new Event("resize")), 220);
    });
  </script>
</body>
</html>
"""
