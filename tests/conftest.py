import os
import sys
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("GITHUB_REPO", "test-org/test-repo")
os.environ.setdefault("DEVIN_API_KEY", "test-devin-key")
os.environ.setdefault("DEVIN_ORG_ID", "test-org-id")
os.environ.setdefault("SCAN_INTERVAL_MINUTES", "5")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app import store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()
