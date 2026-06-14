# Devin Remediation Service

An event-driven automation that scans a GitHub repository for issues labelled `devin-remediate` and spins up [Devin](https://devin.ai) sessions to fix them — opening pull requests with proposed solutions.

## How it works

1. On startup, the service scans the GitHub repo for open issues with the `devin-remediate` label.
2. For each issue, it checks for an existing open PR before creating a Devin session, so restarting the service never triggers duplicate work.
3. If no open PR exists, a Devin session is created with a structured prompt to fix the issue and open a PR.
4. A background loop repeats the scan every `SCAN_INTERVAL_MINUTES` to pick up newly labelled issues.
5. A separate background loop polls the Devin API every 60 seconds to update the status of running sessions. A session is marked completed when Devin reports `status: exit` or `status: running` with `status_detail: finished`; it is marked failed on `error` or `suspended`.
6. A live dashboard at `http://localhost:8000` shows the status of all tasks.

## Quick start

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=your_org/target_repo
DEVIN_API_KEY=your_devin_api_key
DEVIN_ORG_ID=your_devin_org_id
SCAN_INTERVAL_MINUTES=5
```

- `GITHUB_TOKEN` — fine-grained personal access token scoped to the target repository, with **Issues: read and write** (to read issues and post comments) and **Pull requests: read** (to search for existing PRs).
- `DEVIN_API_KEY` — API key for Devin (starts with `cog_`), which you can generate following the instructions [here](https://docs.devin.ai/api-reference/getting-started/teams-quickstart#step-2-generate-an-api-key).
- `DEVIN_ORG_ID` - Organization ID for Devin (starts with `org-`), which you can find under `Settings -> General` in [app.devin.ai](app.devin.ai).

> **Note:** Your Devin account must be linked to the GitHub account that owns the target repository so that Devin can clone the repo and open pull requests on your behalf.

### 2. Run with Docker

Install Docker Desktop and run the following command in the project root:

```bash
docker compose up --build
```

The dashboard will be available at **http://localhost:8000**.
At startup, the app will scan for open issues labelled `devin-remediate` in the target repository.
A background loop will scan every `SCAN_INTERVAL_MINUTES` to pick up newly labelled issues.
You can also trigger a manual scan by using the **Scan Issues** button in the dashboard.
If a Devin session fails, you can retry it by clicking the **Retry Failed** button.

## Architecture decisions

**Stack.** FastAPI + uvicorn for the API server, httpx for HTTP calls to the GitHub and Devin APIs, python-dotenv for configuration. Dependencies are intentionally minimal — no ORM, no task queue, no database.

**No persistent storage.** Session state is kept in an in-memory Python dictionary. This means state is lost on restart, but the service is designed to tolerate that: on startup it re-scans GitHub and uses the live PR state as the source of truth rather than its own store. The trade-off is simplicity over durability — acceptable for a demo, but a production deployment would swap the store for a lightweight database.

**Polling over webhooks.** Rather than using a GitHub webhook, the service polls on a configurable interval. This avoids the need for a public endpoint and makes local development and Docker deployment straightforward with no external infrastructure. In a production deployment, a webhook could be added so that the service is notified immediately when an issue is labelled, but the polling approach is simpler and sufficient for a demo/local deployment.

**Single process, async background tasks.** The periodic scan and session polling loops run as asyncio tasks within the same FastAPI process. This keeps the deployment footprint to a single container with no separate worker process or message broker.

## Project structure

```bash
app/
├── main.py         # FastAPI app, startup, background loop, routes
├── github.py       # GitHub API client
├── devin.py        # Devin API client
├── store.py        # In-memory session store
└── templates/
    └── index.html  # Dashboard
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

