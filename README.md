# Superset Remediation Engine

Event-driven automation that uses the [Devin API](https://docs.devin.ai/api-reference/overview) to remediate code quality issues in [Apache Superset](https://github.com/apache/superset).

## What It Does

```
Open Issues (labeled "remediation")
    ↓  periodic scan / manual trigger
Orchestrator
    ↓  POST /v1/sessions (Devin API)
Devin works autonomously
    ↓  async polling
PR created → comment posted on issue
    ↓
Dashboard tracks everything
```

The system scans a forked Superset repository for issues labeled `remediation`, creates Devin sessions to fix each one, polls for completion, and posts results back to GitHub. A live dashboard provides observability into the process.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A [Devin API token](https://app.devin.ai/settings/api)
- A GitHub personal access token (with `repo` scope)

### 1. Clone and configure

```bash
git clone https://github.com/dsj976/devin-superset-remediation.git
cd devin-superset-remediation
cp .env.example .env
# Edit .env with your tokens
```

### 2. Run

```bash
docker compose up --build
```

The server starts on `http://localhost:8000`. On startup, it automatically scans for open issues labeled `remediation` and dispatches Devin sessions.

### 3. Monitor

- **Dashboard**: http://localhost:8000/dashboard (auto-refreshes every 15s)
- **Status API**: http://localhost:8000/status
- **Health check**: http://localhost:8000/health

### 4. Manual triggers

```bash
# Trigger all open remediation issues
curl -X POST http://localhost:8000/trigger

# Trigger a specific issue
curl -X POST http://localhost:8000/trigger/1
```

## Architecture

| Component | File | Purpose |
|-----------|------|---------|
| FastAPI app | `src/main.py` | HTTP routes, startup lifecycle |
| Orchestrator | `src/orchestrator.py` | Devin session creation & management |
| Poller | `src/poller.py` | Background polling loops |
| GitHub client | `src/github_client.py` | Issue fetching, comment posting |
| Models | `src/models.py` | SQLite persistence layer |
| Dashboard | `src/dashboard.py` | Observability UI (HTML + JSON) |
| Config | `src/config.py` | Environment variable settings |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/dashboard` | Observability dashboard (HTML or JSON) |
| `GET` | `/status` | Current task status (JSON) |
| `POST` | `/trigger` | Scan and dispatch all open issues |
| `POST` | `/trigger/{issue_number}` | Dispatch a specific issue |

## Observability

The dashboard answers: *"If I were an engineering leader, how would I know this is working?"*

- **Total issues** tracked
- **Success rate** (completed / total)
- **Average duration** per remediation
- **Per-issue status** with links to Devin sessions and PRs
- Auto-refreshes every 15 seconds

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEVIN_API_TOKEN` | Devin API bearer token | (required) |
| `GITHUB_TOKEN` | GitHub PAT with repo scope | (required) |
| `TARGET_REPO` | Repository to scan (owner/repo) | `dsj976/superset` |
| `DEVIN_ORG_ID` | Devin organization ID | (required) |
| `TRIGGER_LABEL` | Issue label that triggers remediation | `remediation` |
| `POLL_INTERVAL` | Seconds between status polls | `30` |
| `SCAN_INTERVAL_MINUTES` | Minutes between issue scans (0=off) | `5` |

## Target Repository

The forked Superset repo with issues: https://github.com/dsj976/superset/issues

Issues being remediated:
1. [Add timeout=60 to outbound HTTP requests](https://github.com/dsj976/superset/issues/1)
2. [Replace deprecated datetime.utcnow()](https://github.com/dsj976/superset/issues/2)
3. [Replace legacy typing imports](https://github.com/dsj976/superset/issues/3)
4. [Add explicit encoding="utf-8" to open() calls](https://github.com/dsj976/superset/issues/4)

## License

MIT
