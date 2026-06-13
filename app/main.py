import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

load_dotenv()

from app import devin, github, store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_MINUTES", "5")) * 60
TEMPLATES_DIR = Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# Core scan logic
# ---------------------------------------------------------------------------

def _process_issue(issue: dict, force_retry: bool = False) -> None:
    """
    Decide whether to create/retry a Devin session for a single issue.
    - If a PR already exists on GitHub → mark completed, skip.
    - If already completed in store → skip (unless force_retry=False is irrelevant here).
    - If failed/pending in store (or not in store) → create session.
    force_retry=True re-runs failed/pending entries.
    """
    number = issue["number"]
    title = issue["title"]
    body = issue.get("body") or ""
    issue_url = issue["html_url"]

    current_status = store.get_status(number)

    # 1. Already completed → check GitHub for PR, then skip
    if current_status == "completed":
        return

    # 2. Currently running → don't spawn a duplicate
    if current_status == "running" and not force_retry:
        return

    # 3. Check GitHub for an existing PR (deduplication on restart)
    pr_url = github.find_existing_pr(number)
    if pr_url:
        log.info("Issue #%d already has PR %s — marking completed", number, pr_url)
        store.upsert(number, title=title, issue_url=issue_url, status="completed", pr_url=pr_url)
        return

    # 4. Create a new Devin session
    log.info("Creating Devin session for issue #%d: %s", number, title)
    store.upsert(number, title=title, issue_url=issue_url, status="pending")
    try:
        result = devin.create_session(number, title, body)
        session_id = result.get("session_id") or result.get("id")
        session_url = result.get("url") or result.get("session_url")
        store.upsert(number, session_id=session_id, session_url=session_url, status="running")
        log.info("Session %s created for issue #%d", session_id, number)
        try:
            github.post_comment(
                number,
                f"🤖 A Devin session has been started to address this issue.\n\nSession: {session_url}",
            )
        except Exception as comment_exc:
            log.warning("Could not post comment on issue #%d: %s", number, comment_exc)
    except Exception as exc:
        log.error("Failed to create Devin session for issue #%d: %s", number, exc)
        store.upsert(number, status="failed")


def scan_and_process(force_retry: bool = False) -> dict:
    """
    Fetch labeled issues from GitHub and process each one.
    Returns a summary dict.
    """
    log.info("Starting issue scan (force_retry=%s)", force_retry)
    try:
        issues = github.get_labeled_issues()
    except Exception as exc:
        log.error("Failed to fetch issues from GitHub: %s", exc)
        return {"error": str(exc)}

    log.info("Found %d labeled issue(s)", len(issues))
    for issue in issues:
        _process_issue(issue, force_retry=force_retry)

    return {"scanned": len(issues)}


# ---------------------------------------------------------------------------
# Session status polling
# ---------------------------------------------------------------------------

async def _poll_running_sessions() -> None:
    """Periodically update status of running Devin sessions."""
    while True:
        await asyncio.sleep(60)
        running = [e for e in store.get_all() if e["status"] == "running" and e["session_id"]]
        for entry in running:
            try:
                data = devin.get_session(entry["session_id"])
                new_status = devin.map_devin_status(data.get("status"))
                pr_url = devin.extract_pr_url(data)
                store.upsert(entry["issue_number"], status=new_status, pr_url=pr_url)
                if new_status != "running":
                    log.info(
                        "Session %s for issue #%d → %s",
                        entry["session_id"], entry["issue_number"], new_status,
                    )
            except Exception as exc:
                log.warning("Could not poll session %s: %s", entry["session_id"], exc)


# ---------------------------------------------------------------------------
# Background periodic scan
# ---------------------------------------------------------------------------

async def _periodic_scan() -> None:
    while True:
        await asyncio.sleep(SCAN_INTERVAL)
        log.info("Periodic scan triggered")
        scan_and_process(force_retry=False)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Startup scan...")
    scan_and_process(force_retry=False)
    asyncio.create_task(_periodic_scan())
    asyncio.create_task(_poll_running_sessions())
    yield


app = FastAPI(title="Devin Superset Remediation", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html = (TEMPLATES_DIR / "index.html").read_text()
    return HTMLResponse(content=html)


@app.get("/status")
async def status():
    return JSONResponse(content=store.get_all())


@app.post("/scan")
async def manual_scan(force_retry: bool = False):
    """
    Manually trigger a scan.
    - New issues (no existing PR) → create session.
    - failed/pending → retry if force_retry=True.
    - completed → always skip.
    """
    result = scan_and_process(force_retry=force_retry)
    return JSONResponse(content={"ok": True, **result})
