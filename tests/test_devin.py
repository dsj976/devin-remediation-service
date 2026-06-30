import pytest

from app.devin import extract_pr_url, map_devin_status


@pytest.mark.parametrize(
    ("devin_status", "status_detail", "expected"),
    [
        (None, None, "running"),
        ("exit", None, "completed"),
        ("EXIT", None, "completed"),
        ("error", None, "failed"),
        ("suspended", None, "failed"),
        ("running", "finished", "completed"),
        ("running", None, "running"),
        ("new", None, "running"),
        ("claimed", None, "running"),
        ("resuming", None, "running"),
        ("unknown", None, "running"),
    ],
)
def test_map_devin_status(devin_status, status_detail, expected):
    assert map_devin_status(devin_status, status_detail) == expected


@pytest.mark.parametrize(
    ("session_data", "expected"),
    [
        ({}, None),
        ({"pull_requests": []}, None),
        ({"pull_requests": None}, None),
        ({"pull_requests": [{"pr_url": "https://example.com/pr/1"}]}, "https://example.com/pr/1"),
        (
            {
                "pull_requests": [
                    {"pr_url": "https://example.com/pr/1"},
                    {"pr_url": "https://example.com/pr/2"},
                ]
            },
            "https://example.com/pr/1",
        ),
    ],
)
def test_extract_pr_url(session_data, expected):
    assert extract_pr_url(session_data) == expected
