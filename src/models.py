import aiosqlite
import time
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path("data/remediation.db")


@dataclass
class RemediationTask:
    id: int
    issue_number: int
    issue_title: str
    issue_url: str
    devin_session_id: str | None
    devin_session_url: str | None
    status: str  # pending, running, completed, failed
    pr_url: str | None
    created_at: float
    updated_at: float
    error_message: str | None


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_number INTEGER UNIQUE NOT NULL,
                issue_title TEXT NOT NULL,
                issue_url TEXT NOT NULL,
                devin_session_id TEXT,
                devin_session_url TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                pr_url TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                error_message TEXT
            )
        """)
        await db.commit()


async def get_task_by_issue(issue_number: int) -> RemediationTask | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE issue_number = ?", (issue_number,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return RemediationTask(**dict(row))


async def create_task(issue_number: int, issue_title: str, issue_url: str) -> RemediationTask:
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tasks (issue_number, issue_title, issue_url, status, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (issue_number, issue_title, issue_url, now, now),
        )
        await db.commit()
        task_id = cursor.lastrowid
    return RemediationTask(
        id=task_id,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_url=issue_url,
        devin_session_id=None,
        devin_session_url=None,
        status="pending",
        pr_url=None,
        created_at=now,
        updated_at=now,
        error_message=None,
    )


async def update_task(
    issue_number: int,
    *,
    status: str | None = None,
    devin_session_id: str | None = None,
    devin_session_url: str | None = None,
    pr_url: str | None = None,
    error_message: str | None = None,
) -> None:
    fields: list[str] = []
    values: list[object] = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if devin_session_id is not None:
        fields.append("devin_session_id = ?")
        values.append(devin_session_id)
    if devin_session_url is not None:
        fields.append("devin_session_url = ?")
        values.append(devin_session_url)
    if pr_url is not None:
        fields.append("pr_url = ?")
        values.append(pr_url)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if not fields:
        return
    fields.append("updated_at = ?")
    values.append(time.time())
    values.append(issue_number)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE issue_number = ?",
            values,
        )
        await db.commit()


async def get_all_tasks() -> list[RemediationTask]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [RemediationTask(**dict(row)) for row in rows]


async def get_active_tasks() -> list[RemediationTask]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE status IN ('pending', 'running') ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [RemediationTask(**dict(row)) for row in rows]
