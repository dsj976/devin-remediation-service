import time
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src import models

router = APIRouter()


@router.get("/dashboard")
async def dashboard(request: Request):
    """Render the observability dashboard (HTML or JSON based on Accept header)."""
    tasks = await models.get_all_tasks()
    stats = _compute_stats(tasks)

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({
            "stats": stats,
            "tasks": [_task_to_dict(t) for t in tasks],
        })

    html = _render_dashboard(tasks, stats)
    return HTMLResponse(html)


def _compute_stats(tasks: list[models.RemediationTask]) -> dict:
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    failed = sum(1 for t in tasks if t.status == "failed")
    running = sum(1 for t in tasks if t.status == "running")
    pending = sum(1 for t in tasks if t.status == "pending")

    durations = []
    for t in tasks:
        if t.status == "completed":
            durations.append(t.updated_at - t.created_at)

    avg_duration = sum(durations) / len(durations) if durations else 0
    success_rate = (completed / total * 100) if total > 0 else 0

    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "running": running,
        "pending": pending,
        "success_rate": round(success_rate, 1),
        "avg_duration_seconds": round(avg_duration, 1),
    }


def _task_to_dict(task: models.RemediationTask) -> dict:
    return {
        "issue_number": task.issue_number,
        "issue_title": task.issue_title,
        "issue_url": task.issue_url,
        "status": task.status,
        "devin_session_id": task.devin_session_id,
        "devin_session_url": task.devin_session_url,
        "pr_url": task.pr_url,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "duration_seconds": round(task.updated_at - task.created_at, 1),
        "error_message": task.error_message,
    }


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def _status_badge(status: str) -> str:
    colors = {
        "pending": "#6b7280",
        "running": "#2563eb",
        "completed": "#16a34a",
        "failed": "#dc2626",
    }
    color = colors.get(status, "#6b7280")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{status}</span>'


def _render_dashboard(tasks: list[models.RemediationTask], stats: dict) -> str:
    rows = ""
    for t in tasks:
        duration = _format_duration(t.updated_at - t.created_at)
        pr_link = f'<a href="{t.pr_url}" target="_blank">View PR</a>' if t.pr_url else "—"
        session_link = (
            f'<a href="{t.devin_session_url}" target="_blank">{t.devin_session_id[:8]}...</a>'
            if t.devin_session_id
            else "—"
        )
        rows += f"""
        <tr>
            <td><a href="{t.issue_url}" target="_blank">#{t.issue_number}</a></td>
            <td>{t.issue_title}</td>
            <td>{_status_badge(t.status)}</td>
            <td>{session_link}</td>
            <td>{pr_link}</td>
            <td>{duration}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Superset Remediation Dashboard</title>
    <meta http-equiv="refresh" content="15">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; padding: 2rem; }}
        .header {{ margin-bottom: 2rem; }}
        .header h1 {{ color: #1e293b; font-size: 1.5rem; }}
        .header p {{ color: #64748b; margin-top: 0.25rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat-card {{ background: white; border-radius: 8px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-card .value {{ font-size: 2rem; font-weight: 700; color: #1e293b; }}
        .stat-card .label {{ font-size: 0.875rem; color: #64748b; margin-top: 0.25rem; }}
        table {{ width: 100%; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-collapse: collapse; }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f1f5f9; font-weight: 600; color: #475569; font-size: 0.875rem; }}
        td {{ color: #334155; font-size: 0.875rem; }}
        a {{ color: #2563eb; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .updated {{ color: #94a3b8; font-size: 0.75rem; margin-top: 1rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Superset Remediation Dashboard</h1>
        <p>Event-driven code quality remediation powered by Devin</p>
    </div>
    <div class="stats">
        <div class="stat-card">
            <div class="value">{stats['total']}</div>
            <div class="label">Total Issues</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#16a34a">{stats['completed']}</div>
            <div class="label">Completed</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#2563eb">{stats['running']}</div>
            <div class="label">Running</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#dc2626">{stats['failed']}</div>
            <div class="label">Failed</div>
        </div>
        <div class="stat-card">
            <div class="value">{stats['success_rate']}%</div>
            <div class="label">Success Rate</div>
        </div>
        <div class="stat-card">
            <div class="value">{_format_duration(stats['avg_duration_seconds'])}</div>
            <div class="label">Avg Duration</div>
        </div>
    </div>
    <table>
        <thead>
            <tr>
                <th>Issue</th>
                <th>Title</th>
                <th>Status</th>
                <th>Devin Session</th>
                <th>PR</th>
                <th>Duration</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    <p class="updated">Auto-refreshes every 15s | Last updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}</p>
</body>
</html>"""
