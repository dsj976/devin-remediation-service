"""
In-memory store for tracking GitHub issues, their associated Devin sessions,
and processing statuses. All mutations are guarded by a threading lock to
prevent race conditions between the background polling and scanning tasks,
which run concurrently and both write to the store.
"""

import threading
from datetime import datetime, timezone

_lock = threading.Lock()

# Schema per store entry:
# {
#   "issue_number": int,
#   "title": str,
#   "issue_url": str,
#   "session_id": str | None,
#   "session_url": str | None,
#   "status": "running" | "completed" | "failed",
#   "pr_url": str | None,
#   "created_at": str (ISO),
#   "updated_at": str (ISO),
# }

_store: dict[int, dict] = {}  # in-memory store keyed by issue number


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def upsert(issue_number: int, **kwargs) -> dict:
    """Insert a new entry or update an existing one for the given issue number."""
    with _lock:
        if issue_number not in _store:
            _store[issue_number] = {
                "issue_number": issue_number,
                "title": kwargs.get("title", ""),
                "issue_url": kwargs.get("issue_url", ""),
                "session_id": None,
                "session_url": None,
                "status": "running",
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


def get(issue_number: int) -> dict | None:
    """Retrieve the entry for the given issue number."""
    with _lock:
        entry = _store.get(issue_number)
        return dict(entry) if entry else None


def get_all() -> list:
    """Return a list of all entries in the store, sorted by issue number."""
    with _lock:
        return [
            dict(v) for v in sorted(_store.values(), key=lambda x: x["issue_number"])
        ]


def get_status(issue_number: int) -> str | None:
    """Return the current status of the given issue number."""
    with _lock:
        entry = _store.get(issue_number)
        return entry["status"] if entry else None
