import os

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


def get_labeled_issues() -> list[dict]:
    """Return all open issues tagged with LABEL."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues"
    params = {"labels": LABEL, "state": "open", "per_page": 100}
    with httpx.Client() as client:
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
    issues = resp.json()
    # Exclude pull requests (GitHub returns PRs as issues too)
    return [i for i in issues if "pull_request" not in i]


def find_existing_pr(issue_number: int) -> str | None:
    """
    Return the HTML URL of any open PR that references this issue, or None.

    Two checks are performed in order:
    1. Issue timeline cross-referenced events — covers PRs that use GitHub's
       closing keywords (Fixes/Closes/Resolves #N) in their body.
    2. Full open-PR scan — covers PRs that mention #N only in their title (e.g.
       the format Devin uses: "Fix #N: Title") and never produce a timeline event.
    """
    owner, repo = _repo().split("/", 1)

    # --- check 1: timeline cross-references ---
    timeline_url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/timeline"
    with httpx.Client() as client:
        resp = client.get(timeline_url, headers=_headers(), params={"per_page": 100})
        resp.raise_for_status()
    for event in resp.json():
        if event.get("event") != "cross-referenced":
            continue
        source_issue = event.get("source", {}).get("issue", {})
        if source_issue.get("pull_request") and source_issue.get("state") == "open":
            return source_issue["html_url"]

    # --- check 2: scan open PRs for title/body mention of #issue_number ---
    prs_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
    needle = f"#{issue_number}"
    with httpx.Client() as client:
        resp = client.get(prs_url, headers=_headers(), params={"state": "open", "per_page": 100})
        resp.raise_for_status()
    for pr in resp.json():
        title = pr.get("title", "")
        body = pr.get("body") or ""
        if needle in title or needle in body:
            return pr["html_url"]

    return None


def post_comment(issue_number: int, body: str) -> None:
    """Post a comment on a GitHub issue."""
    url = f"{GITHUB_API}/repos/{_repo()}/issues/{issue_number}/comments"
    with httpx.Client() as client:
        resp = client.post(url, headers=_headers(), json={"body": body})
        resp.raise_for_status()
