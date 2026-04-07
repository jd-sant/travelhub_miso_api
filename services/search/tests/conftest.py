import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite://"

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from entrypoints.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
