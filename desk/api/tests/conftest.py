import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def app(tmp_path):
    from desk.api.app import create_app

    return create_app(db_path=tmp_path / "t.db")


@pytest.fixture
def client(app):
    return app.test_client()
