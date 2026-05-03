from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _load_sessions(sessions_dir: Path) -> list[dict]:
    sessions: list[dict] = []
    if not sessions_dir.exists():
        return sessions
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            data["_source_file"] = str(path)
            sessions.append(data)
        except Exception:
            continue
    return sessions


def _format_ts(ts: str) -> str:
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def _fmt_ms(ms: int) -> str:
    if ms <= 0:
        return "0ms"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


def _state_color(state: str) -> str:
    colors = {
        "idle": "#6b7280",
        "awaiting_clarification": "#f59e0b",
        "recommended": "#10b981",
        "refining": "#6366f1",
    }
    return colors.get(state, "#6b7280")


def _build_html(sessions: list[dict], sessions_dir: Path) -> str:
    total_sessions = len(sessions)
    total_turns = sum(s.get("analytics", {}).get("turn_count", 0) for s in sessions)
    total_errors = sum(s.get("analytics", {}).get("error_count", 0) for s in sessions)
    total_clarifications = sum(s.get("analytics", {}).get("clarification_turn_count", 0) for s in sessions)
    total_refinements = sum(s.get("analytics", {}).get("refinement_round_count", 0) for s in sessions)
    total_recommendations = sum(s.get("analytics", {}).get("recommendation_round_count", 0) for s in sessions)
    total_fallbacks = sum(s.get("analytics", {}).get("fallback_count", 0) for s in sessions)
    total_enrichment = sum(s.get("analytics", {}).get("enrichment_used_count", 0) for s in sessions)

    avg_turns = round(total_turns / total_sessions, 1) if total_sessions else 0
    avg_latency = 0
    latencies = [s.get("analytics", {}).get("last_latency_ms", 0) for s in sessions if s.get("analytics", {}).get("last_latency_ms", 0) > 0]
    if latencies:
        avg_latency = round(sum(latencies) / len(latencies), 0)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rows_html = []
    for s in sessions:
        a = s.get("analytics", {})
        sid = s.get("session_id", "unknown")[:12]
        state = s.get("state", "unknown")
        color = _state_color(state)
        turns = a.get("turn_count", 0)
        clarifications = a.get("clarification_turn_count", 0)
        refinements = a.get("refinement_round_count", 0)
        rec_rounds = a.get("recommendation_round_count", 0)
        errors = a.get("error_count", 0)
        total_lat = a.get("total_latency_ms", 0)
        last_lat = a.get("last_latency_ms", 0)
        rec_count = a.get("recommended_titles_count", 0)
        unique_count = a.get("unique_titles_count", 0)
        fallbacks = a.get("fallback_count", 0)
        enrichment = a.get("enrichment_used_count", 0)
        started = _format_ts(a.get("started_at", ""))
        updated = _format_ts(a.get("last_updated_at", ""))
        last_type = a.get("last_response_type", "")

        shown = s.get("shown_titles", [])
        rejected = s.get("rejected_titles", [])
        last_recs = s.get("last_recommendations", [])
        accepted_prefs = s.get("accepted_soft_preferences", {})
        rejected_prefs = s.get("rejected_soft_preferences", {})
        ext_signals = s.get("external_signal_history", [])
        feedback_count = len(s.get("feedback_signals", []))

        rec_titles = [r.get("title", "") for r in last_recs if isinstance(r, dict)]

        rows_html.append(f"""
        <details class="session-detail">
            <summary>
                <span class="session-id">{sid}...</span>
                <span class="state-badge" style="background:{color}">{state}</span>
                <span class="meta">{turns} turns</span>
                <span class="meta">{_fmt_ms(total_lat)} total</span>
                <span class="meta">{started}</span>
            </summary>
            <div class="session-body">
                <table class="detail-table">
                    <tr><th>Session ID</th><td>{s.get('session_id', '')}</td></tr>
                    <tr><th>State</th><td>{state}</td></tr>
                    <tr><th>Started</th><td>{started}</td></tr>
                    <tr><th>Last Updated</th><td>{updated}</td></tr>
                    <tr><th>Turns</th><td>{turns} (user: {a.get('user_turn_count', 0)}, assistant: {a.get('assistant_turn_count', 0)})</td></tr>
                    <tr><th>Clarifications</th><td>{clarifications}</td></tr>
                    <tr><th>Recommendation Rounds</th><td>{rec_rounds}</td></tr>
                    <tr><th>Refinement Rounds</th><td>{refinements}</td></tr>
                    <tr><th>Errors</th><td>{errors}</td></tr>
                    <tr><th>Fallbacks</th><td>{fallbacks}</td></tr>
                    <tr><th>Enrichment Used</th><td>{enrichment}</td></tr>
                    <tr><th>Total Latency</th><td>{_fmt_ms(total_lat)}</td></tr>
                    <tr><th>Last Latency</th><td>{_fmt_ms(last_lat)}</td></tr>
                    <tr><th>Last Response Type</th><td>{last_type}</td></tr>
                    <tr><th>Recommended Titles</th><td>{rec_count}</td></tr>
                    <tr><th>Unique Titles Shown</th><td>{unique_count}</td></tr>
                    <tr><th>Feedback Signals</th><td>{feedback_count}</td></tr>
                    <tr><th>External Signals</th><td>{', '.join(ext_signals) if ext_signals else 'none'}</td></tr>
                    <tr><th>Accepted Preferences</th><td>{json.dumps(accepted_prefs, ensure_ascii=False) if accepted_prefs else 'none'}</td></tr>
                    <tr><th>Rejected Preferences</th><td>{json.dumps(rejected_prefs, ensure_ascii=False) if rejected_prefs else 'none'}</td></tr>
                    <tr><th>Shown Titles</th><td>{', '.join(shown) if shown else 'none'}</td></tr>
                    <tr><th>Rejected Titles</th><td>{', '.join(rejected) if rejected else 'none'}</td></tr>
                    <tr><th>Last Recommendations</th><td>{', '.join(rec_titles) if rec_titles else 'none'}</td></tr>
                </table>
                <div class="raw-json">
                    <details>
                        <summary>Raw JSON</summary>
                        <pre>{json.dumps(s, indent=2, ensure_ascii=False)}</pre>
                    </details>
                </div>
            </div>
        </details>
        """)

    rows = "\n".join(rows_html)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Netflix Agent — Observability Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; color: #1f2937; padding: 24px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 24px; margin-bottom: 4px; }}
        .subtitle {{ color: #6b7280; font-size: 14px; margin-bottom: 24px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 32px; }}
        .summary-card {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .summary-card .value {{ font-size: 28px; font-weight: 700; color: #111827; }}
        .summary-card .label {{ font-size: 12px; color: #6b7280; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .session-detail {{ background: white; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .session-detail summary {{ padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 12px; list-style: none; }}
        .session-detail summary::-webkit-details-marker {{ display: none; }}
        .session-detail summary::before {{ content: "\u25B6"; font-size: 10px; color: #9ca3af; transition: transform 0.15s; }}
        .session-detail[open] summary::before {{ transform: rotate(90deg); }}
        .session-id {{ font-family: monospace; font-size: 13px; color: #6366f1; }}
        .state-badge {{ font-size: 11px; color: white; padding: 2px 8px; border-radius: 12px; font-weight: 600; }}
        .meta {{ font-size: 12px; color: #9ca3af; }}
        .session-body {{ padding: 0 16px 16px; border-top: 1px solid #e5e7eb; }}
        .detail-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
        .detail-table th {{ text-align: left; padding: 6px 8px; background: #f9fafb; color: #6b7280; font-weight: 500; width: 200px; }}
        .detail-table td {{ padding: 6px 8px; border-top: 1px solid #e5e7eb; word-break: break-word; }}
        .raw-json {{ margin-top: 12px; }}
        .raw-json pre {{ background: #1f2937; color: #e5e7eb; padding: 12px; border-radius: 6px; font-size: 11px; overflow-x: auto; max-height: 400px; overflow-y: auto; }}
        .no-sessions {{ text-align: center; padding: 48px; color: #9ca3af; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Netflix Agent — Observability Report</h1>
        <p class="subtitle">Generated: {now} | Sessions directory: {sessions_dir}</p>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{total_sessions}</div>
                <div class="label">Sessions</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_turns}</div>
                <div class="label">Total Turns</div>
            </div>
            <div class="summary-card">
                <div class="value">{avg_turns}</div>
                <div class="label">Avg Turns / Session</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_recommendations}</div>
                <div class="label">Recommendation Rounds</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_clarifications}</div>
                <div class="label">Clarifications</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_refinements}</div>
                <div class="label">Refinements</div>
            </div>
            <div class="summary-card">
                <div class="value">{_fmt_ms(int(avg_latency))}</div>
                <div class="label">Avg Last Turn Latency</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_errors}</div>
                <div class="label">Errors</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_fallbacks}</div>
                <div class="label">Fallbacks</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_enrichment}</div>
                <div class="label">Enrichment Used</div>
            </div>
        </div>

        <h2 style="font-size: 18px; margin-bottom: 12px;">Sessions</h2>

        {rows if rows else '<div class="no-sessions">No sessions found. Start a chat session first.</div>'}
    </div>
</body>
</html>"""
    return html


def generate_report(
    sessions_dir: str | Path | None = None,
    output_path: str | Path | None = None,
) -> Path:
    if sessions_dir is None:
        sessions_dir = os.getenv("SESSIONS_DIR", "memory/sessions")
    sessions_dir = Path(sessions_dir)

    if output_path is None:
        output_path = Path("logs/observability_report.html")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sessions = _load_sessions(sessions_dir)
    html = _build_html(sessions, sessions_dir)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    report_path = generate_report()
    print(f"Observability report generated: {report_path}")
    print(f"Open it in your browser to view session analytics.")
