import os
from typing import List, Optional

import httpx

GITHUB_API = "https://api.github.com"
LABEL = "devin-remediate"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo() -> str:
    return os.environ["GITHUB_REPO"]


def get_labeled_issues() -> List[dict]:
    """Return all open issues tagged with LABEL."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues"
    params = {"labels": LABEL, "state": "open", "per_page": 100}
    with httpx.Client() as client:
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
    issues = resp.json()
    # Exclude pull requests (GitHub returns PRs as issues too)
    return [i for i in issues if "pull_request" not in i]


def find_existing_pr(issue_number: int) -> Optional[str]:
    """
    Check the issue timeline for cross-referenced events from open PRs.
    This is more reliable than text search — it only returns PRs that GitHub
    explicitly linked to this issue (e.g. via 'Fixes #N' or the UI linker).
    Closed/merged PRs are ignored — if the issue is still open, it still needs work.
    Returns the PR HTML URL if found, else None.
    """
    owner, repo = _repo().split("/", 1)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/timeline"
    params = {"per_page": 100}
    with httpx.Client() as client:
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
    for event in resp.json():
        if event.get("event") != "cross-referenced":
            continue
        source = event.get("source", {})
        source_issue = source.get("issue", {})
        pr = source_issue.get("pull_request", {})
        if not pr:
            continue
        # Only count the PR if it is still open
        if source_issue.get("state") == "open":
            return source_issue.get("html_url")
    return None


def post_comment(issue_number: int, body: str) -> None:
    """Post a comment on a GitHub issue."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues/{issue_number}/comments"
    with httpx.Client() as client:
        resp = client.post(url, headers=_headers(), json={"body": body})
        resp.raise_for_status()
