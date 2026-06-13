import threading
from datetime import datetime, timezone
from typing import Dict, Optional

_lock = threading.Lock()

# Schema per entry:
# {
#   "issue_number": int,
#   "title": str,
#   "issue_url": str,
#   "session_id": str | None,
#   "session_url": str | None,
#   "status": "pending" | "running" | "completed" | "failed",
#   "pr_url": str | None,
#   "created_at": str (ISO),
#   "updated_at": str (ISO),
# }

_store: Dict[int, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert(issue_number: int, **kwargs) -> dict:
    with _lock:
        if issue_number not in _store:
            _store[issue_number] = {
                "issue_number": issue_number,
                "title": kwargs.get("title", ""),
                "issue_url": kwargs.get("issue_url", ""),
                "session_id": None,
                "session_url": None,
                "status": "pending",
                "pr_url": None,
                "created_at": _now(),
                "updated_at": _now(),
            }
        entry = _store[issue_number]
        for k, v in kwargs.items():
            if k in entry and v is not None:
                entry[k] = v
        entry["updated_at"] = _now()
        return dict(entry)


def get(issue_number: int) -> Optional[dict]:
    with _lock:
        entry = _store.get(issue_number)
        return dict(entry) if entry else None


def get_all() -> list:
    with _lock:
        return [dict(v) for v in sorted(_store.values(), key=lambda x: x["issue_number"])]


def get_status(issue_number: int) -> Optional[str]:
    with _lock:
        entry = _store.get(issue_number)
        return entry["status"] if entry else None
