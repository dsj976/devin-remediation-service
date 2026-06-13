import httpx
import logging

from src.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
    }


async def fetch_open_issues(label: str | None = None) -> list[dict]:
    """Fetch open issues from the target repository, optionally filtered by label."""
    url = f"{GITHUB_API}/repos/{settings.target_repo}/issues"
    params: dict[str, str] = {"state": "open", "per_page": "100"}
    if label:
        params["labels"] = label
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        # Filter out pull requests (GitHub API returns PRs in the issues endpoint)
        issues = [i for i in resp.json() if "pull_request" not in i]
        logger.info(f"Fetched {len(issues)} open issues (label={label})")
        return issues


async def get_issue(issue_number: int) -> dict:
    """Fetch a single issue by number."""
    url = f"{GITHUB_API}/repos/{settings.target_repo}/issues/{issue_number}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def post_comment(issue_number: int, body: str) -> None:
    """Post a comment on a GitHub issue."""
    url = f"{GITHUB_API}/repos/{settings.target_repo}/issues/{issue_number}/comments"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=_headers(), json={"body": body})
        resp.raise_for_status()
        logger.info(f"Posted comment on issue #{issue_number}")


async def add_label(issue_number: int, label: str) -> None:
    """Add a label to an issue."""
    url = f"{GITHUB_API}/repos/{settings.target_repo}/issues/{issue_number}/labels"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=_headers(), json={"labels": [label]})
        resp.raise_for_status()
