import httpx
import logging
import asyncio

from src.config import settings
from src import models
from src import github_client

logger = logging.getLogger(__name__)

DEVIN_API = "https://api.devin.ai/v1"


def _devin_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.devin_api_token}",
        "Content-Type": "application/json",
    }


def _build_prompt(issue: dict) -> str:
    """Build a Devin session prompt from the GitHub issue."""
    return (
        f"Fix the following issue in the repository {settings.target_repo}.\n\n"
        f"## Issue #{issue['number']}: {issue['title']}\n\n"
        f"{issue['body']}\n\n"
        f"---\n"
        f"Instructions:\n"
        f"- Clone the repository https://github.com/{settings.target_repo}\n"
        f"- Make the changes described in the issue above\n"
        f"- Create a pull request with a clear title and description\n"
        f"- Reference the issue (Fixes #{issue['number']}) in the PR description\n"
        f"- Ensure the code follows the existing style conventions in the repository\n"
    )


async def create_devin_session(issue_number: int) -> None:
    """Create a Devin session to remediate a specific issue."""
    task = await models.get_task_by_issue(issue_number)
    if task is None:
        logger.error(f"No task found for issue #{issue_number}")
        return
    if task.status not in ("pending",):
        logger.info(f"Task for issue #{issue_number} already {task.status}, skipping")
        return

    issue = await github_client.get_issue(issue_number)
    prompt = _build_prompt(issue)

    logger.info(f"Creating Devin session for issue #{issue_number}: {issue['title']}")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{DEVIN_API}/sessions",
            headers=_devin_headers(),
            json={"prompt": prompt},
        )
        resp.raise_for_status()
        data = resp.json()

    session_id = data.get("session_id", "")
    session_url = data.get("url", f"https://app.devin.ai/sessions/{session_id}")

    await models.update_task(
        issue_number,
        status="running",
        devin_session_id=session_id,
        devin_session_url=session_url,
    )

    await github_client.post_comment(
        issue_number,
        f"Devin session created to remediate this issue.\n\n"
        f"Session: {session_url}\n\n"
        f"Status: **running**",
    )
    logger.info(f"Devin session {session_id} created for issue #{issue_number}")


async def check_session_status(task: models.RemediationTask) -> None:
    """Poll a Devin session for completion and update the task."""
    if not task.devin_session_id:
        return

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{DEVIN_API}/session/{task.devin_session_id}",
            headers=_devin_headers(),
        )
        if resp.status_code == 404:
            logger.warning(f"Session {task.devin_session_id} not found")
            return
        resp.raise_for_status()
        data = resp.json()

    status = data.get("status_enum", "unknown")

    if status == "finished":
        pr_url = _extract_pr_url(data)
        await models.update_task(
            task.issue_number,
            status="completed",
            pr_url=pr_url or "",
        )
        comment = "Devin has completed the remediation.\n\n"
        if pr_url:
            comment += f"Pull Request: {pr_url}"
        else:
            comment += "No PR URL detected — please check the session for details."
        await github_client.post_comment(task.issue_number, comment)
        logger.info(f"Issue #{task.issue_number} remediated. PR: {pr_url}")

    elif status == "stopped":
        await models.update_task(
            task.issue_number,
            status="failed",
            error_message="Session was stopped",
        )
        await github_client.post_comment(
            task.issue_number,
            "Devin session was stopped before completion. Status: **failed**",
        )
        logger.warning(f"Session for issue #{task.issue_number} was stopped")

    elif status == "blocked":
        logger.info(f"Session for issue #{task.issue_number} is blocked (waiting for input)")


def _extract_pr_url(session_data: dict) -> str | None:
    """Extract PR URL from Devin session data."""
    # Check structured_output first
    structured = session_data.get("structured_output", {})
    if structured:
        pr_links = structured.get("pull_request_links", [])
        if pr_links:
            return pr_links[0]
    return None


async def poll_active_sessions() -> None:
    """Poll all active sessions for status updates."""
    active_tasks = await models.get_active_tasks()
    for task in active_tasks:
        if task.status == "pending" and not task.devin_session_id:
            await create_devin_session(task.issue_number)
            await asyncio.sleep(2)  # Brief pause between session creations
        elif task.status == "running" and task.devin_session_id:
            await check_session_status(task)
            await asyncio.sleep(1)


async def dispatch_issue(issue: dict) -> models.RemediationTask:
    """Register an issue for remediation and kick off a Devin session."""
    existing = await models.get_task_by_issue(issue["number"])
    if existing:
        logger.info(f"Issue #{issue['number']} already tracked (status: {existing.status})")
        return existing

    task = await models.create_task(
        issue_number=issue["number"],
        issue_title=issue["title"],
        issue_url=issue["html_url"],
    )
    logger.info(f"Dispatched issue #{issue['number']}: {issue['title']}")

    # Immediately create the Devin session
    await create_devin_session(issue["number"])
    return task


async def scan_and_dispatch() -> list[models.RemediationTask]:
    """Scan for open issues with the trigger label and dispatch new ones."""
    issues = await github_client.fetch_open_issues(label=settings.trigger_label)
    dispatched = []
    for issue in issues:
        task = await dispatch_issue(issue)
        dispatched.append(task)
    return dispatched
