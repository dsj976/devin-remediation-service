from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    devin_api_token: str = ""
    github_token: str = ""
    target_repo: str = "dsj976/superset"
    devin_org_id: str = ""
    trigger_label: str = "remediation"
    poll_interval: int = 30
    scan_interval_minutes: int = 5
    database_url: str = "sqlite+aiosqlite:///./data/remediation.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
