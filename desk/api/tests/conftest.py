import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def app(tmp_path):
    from desk.api.app import create_app

    app = create_app(db_path=tmp_path / "t.db")
    # Ninguna prueba toca la base ni el ejecutable reales de MarketDataFeed, ni sale a internet.
    app.config["MDF_DB"] = str(tmp_path / "no-existe" / "sofr.db")
    app.config["MDF_FETCH"] = str(tmp_path / "no-existe" / "fetch_sofr")
    app.config["FRED_DEXMXUS_URL"] = (tmp_path / "no-existe" / "fred.csv").as_uri()
    return app


@pytest.fixture
def client(app):
    return app.test_client()
