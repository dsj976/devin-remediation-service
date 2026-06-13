import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import settings
from src import models
from src.orchestrator import scan_and_dispatch, dispatch_issue
from src.poller import polling_loop, scan_loop
from src.dashboard import router as dashboard_router
from src.github_client import get_issue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, run initial scan, start background tasks."""
    await models.init_db()
    logger.info("Database initialized")

    # Initial scan for open issues
    logger.info(f"Scanning {settings.target_repo} for issues labeled '{settings.trigger_label}'...")
    try:
        dispatched = await scan_and_dispatch()
        logger.info(f"Initial scan complete: {len(dispatched)} issues tracked")
    except Exception as e:
        logger.error(f"Initial scan failed: {e}")

    # Start background polling
    poll_task = asyncio.create_task(polling_loop())
    scan_task = asyncio.create_task(scan_loop())

    yield

    poll_task.cancel()
    scan_task.cancel()


app = FastAPI(
    title="Superset Remediation Engine",
    description="Event-driven automation that uses Devin to remediate code quality issues",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(dashboard_router)


class TriggerRequest(BaseModel):
    issue_number: int | None = None


class TriggerAllResponse(BaseModel):
    message: str
    tasks_dispatched: int


@app.get("/health")
async def health():
    return {"status": "healthy", "target_repo": settings.target_repo}


@app.post("/trigger")
async def trigger(req: TriggerRequest | None = None):
    """Manually trigger remediation for a specific issue or all open labeled issues."""
    if req and req.issue_number:
        issue = await get_issue(req.issue_number)
        task = await dispatch_issue(issue)
        return {
            "message": f"Dispatched issue #{req.issue_number}",
            "task_status": task.status,
            "devin_session_id": task.devin_session_id,
        }

    # Trigger all open labeled issues
    dispatched = await scan_and_dispatch()
    return TriggerAllResponse(
        message=f"Scanned and dispatched {len(dispatched)} issues",
        tasks_dispatched=len(dispatched),
    )


@app.post("/trigger/{issue_number}")
async def trigger_issue(issue_number: int):
    """Trigger remediation for a specific issue by number."""
    try:
        issue = await get_issue(issue_number)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Issue #{issue_number} not found: {e}")
    task = await dispatch_issue(issue)
    return {
        "message": f"Dispatched issue #{issue_number}",
        "task_status": task.status,
        "devin_session_id": task.devin_session_id,
    }


@app.get("/status")
async def status():
    """Get current status of all remediation tasks."""
    tasks = await models.get_all_tasks()
    return {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.status == "completed"),
        "running": sum(1 for t in tasks if t.status == "running"),
        "failed": sum(1 for t in tasks if t.status == "failed"),
        "pending": sum(1 for t in tasks if t.status == "pending"),
        "tasks": [
            {
                "issue_number": t.issue_number,
                "issue_title": t.issue_title,
                "status": t.status,
                "pr_url": t.pr_url,
                "devin_session_url": t.devin_session_url,
            }
            for t in tasks
        ],
    }
