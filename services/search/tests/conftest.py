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
from db.seed import seed_dummy_data_if_needed
from db.session import create_db_and_tables


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def seed_dummy_data_for_local_db(client):
    create_db_and_tables()
    seed_dummy_data_if_needed()
