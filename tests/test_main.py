import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import devin, github, main, store


def test_dashboard_returns_html():
    client = TestClient(main.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text
    assert "Devin" in response.text


def test_status_returns_store_entries_as_json():
    store.upsert(12, title="Issue 12", issue_url="https://example.com/issues/12")
    store.upsert(3, title="Issue 3", issue_url="https://example.com/issues/3")
    client = TestClient(main.app)

    response = client.get("/status")

    assert response.status_code == 200
    assert [entry["issue_number"] for entry in response.json()] == [3, 12]


def test_manual_scan_triggers_scan_and_returns_result(monkeypatch):
    calls = []

    def fake_scan_and_process(force_retry=False):
        calls.append(force_retry)
        return {"scanned": 2}

    monkeypatch.setattr(main, "scan_and_process", fake_scan_and_process)
    client = TestClient(main.app)

    response = client.post("/scan")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "scanned": 2}
    assert calls == [False]


def test_process_issue_creates_session_and_comments(monkeypatch):
    issue = {
        "number": 1,
        "title": "Fix bug",
        "body": "Details",
        "html_url": "https://example.com/issues/1",
    }
    session_calls = []
    comment_calls = []

    monkeypatch.setattr(github, "find_existing_pr", lambda number: None)

    def fake_create_session(number, title, body):
        session_calls.append((number, title, body))
        return {"session_id": "sess-1", "url": "https://example.com/sessions/1"}

    def fake_post_comment(number, body):
        comment_calls.append((number, body))

    monkeypatch.setattr(devin, "create_session", fake_create_session)
    monkeypatch.setattr(github, "post_comment", fake_post_comment)

    main._process_issue(issue)

    assert session_calls == [(1, "Fix bug", "Details")]
    assert comment_calls == [
        (
            1,
            "🤖 A Devin session has been started to address this issue.\n\nSession: https://example.com/sessions/1",
        )
    ]
    entry = store.get(1)
    assert entry["status"] == "running"
    assert entry["session_id"] == "sess-1"
    assert entry["session_url"] == "https://example.com/sessions/1"


def test_process_issue_marks_existing_pr_completed_and_skips_session(monkeypatch):
    issue = {
        "number": 2,
        "title": "Fix bug",
        "body": "Details",
        "html_url": "https://example.com/issues/2",
    }
    monkeypatch.setattr(
        github, "find_existing_pr", lambda number: "https://example.com/pr/2"
    )

    create_session_calls = []
    monkeypatch.setattr(
        devin,
        "create_session",
        lambda *args, **kwargs: create_session_calls.append((args, kwargs)),
    )

    main._process_issue(issue)

    assert create_session_calls == []
    entry = store.get(2)
    assert entry["status"] == "completed"
    assert entry["pr_url"] == "https://example.com/pr/2"


def test_process_issue_skips_when_running(monkeypatch):
    issue = {
        "number": 3,
        "title": "Fix bug",
        "body": "Details",
        "html_url": "https://example.com/issues/3",
    }
    store.upsert(3, title="Fix bug", issue_url="https://example.com/issues/3", status="running")
    monkeypatch.setattr(github, "find_existing_pr", lambda number: None)
    create_session_calls = []
    monkeypatch.setattr(
        devin,
        "create_session",
        lambda *args, **kwargs: create_session_calls.append((args, kwargs)),
    )

    main._process_issue(issue)

    assert create_session_calls == []
    assert store.get_status(3) == "running"


def test_process_issue_skips_failed_without_force_retry(monkeypatch):
    issue = {
        "number": 4,
        "title": "Fix bug",
        "body": "Details",
        "html_url": "https://example.com/issues/4",
    }
    store.upsert(4, title="Fix bug", issue_url="https://example.com/issues/4", status="failed")
    monkeypatch.setattr(github, "find_existing_pr", lambda number: None)
    create_session_calls = []
    monkeypatch.setattr(
        devin,
        "create_session",
        lambda *args, **kwargs: create_session_calls.append((args, kwargs)),
    )

    main._process_issue(issue, force_retry=False)

    assert create_session_calls == []


def test_process_issue_retries_failed_when_force_retry_true(monkeypatch):
    issue = {
        "number": 5,
        "title": "Fix bug",
        "body": "Details",
        "html_url": "https://example.com/issues/5",
    }
    store.upsert(5, title="Fix bug", issue_url="https://example.com/issues/5", status="failed")
    monkeypatch.setattr(github, "find_existing_pr", lambda number: None)
    monkeypatch.setattr(devin, "create_session", lambda *args: {"session_id": "sess-5", "url": "https://example.com/sessions/5"})
    monkeypatch.setattr(github, "post_comment", lambda *args, **kwargs: None)

    main._process_issue(issue, force_retry=True)

    assert store.get(5)["status"] == "running"
    assert store.get(5)["session_id"] == "sess-5"
    assert store.get(5)["session_url"] == "https://example.com/sessions/5"


@pytest.mark.asyncio
async def test_poll_running_sessions_marks_completed_from_devin_exit(monkeypatch):
    store.upsert(
        10,
        title="Fix bug",
        issue_url="https://example.com/issues/10",
        session_id="sess-10",
        session_url="https://example.com/sessions/10",
        status="running",
    )

    monkeypatch.setattr(
        devin,
        "get_session",
        lambda session_id: {
            "status": "exit",
            "status_detail": None,
            "pull_requests": [{"pr_url": "https://example.com/pr/10"}],
        },
    )
    monkeypatch.setattr(github, "find_existing_pr", lambda issue_number: None)

    calls = {"count": 0}

    async def fake_sleep(seconds):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await main._poll_running_sessions()

    entry = store.get(10)
    assert entry["status"] == "completed"
    assert entry["pr_url"] == "https://example.com/pr/10"


@pytest.mark.asyncio
async def test_poll_running_sessions_marks_completed_from_github_fallback(monkeypatch):
    store.upsert(
        11,
        title="Fix bug",
        issue_url="https://example.com/issues/11",
        session_id="sess-11",
        session_url="https://example.com/sessions/11",
        status="running",
    )

    monkeypatch.setattr(
        devin,
        "get_session",
        lambda session_id: {
            "status": "running",
            "status_detail": None,
            "pull_requests": [],
        },
    )
    monkeypatch.setattr(
        github, "find_existing_pr", lambda issue_number: "https://example.com/pr/11"
    )

    calls = {"count": 0}

    async def fake_sleep(seconds):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await main._poll_running_sessions()

    entry = store.get(11)
    assert entry["status"] == "completed"
    assert entry["pr_url"] == "https://example.com/pr/11"
