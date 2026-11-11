"""Aplicación Flask del QF Desk: API en /api/* y, si existe, la UI construida en /."""
import os
from pathlib import Path
from typing import Optional, Union

from flask import Flask, Response, send_from_directory
from werkzeug.exceptions import NotFound
from werkzeug.utils import safe_join

from desk.api import db, fred
from desk.api.errors import register_error_handlers
from desk.api.routes import fixings, hedges, market, pnl, price, risk, trades
from desk.api.routes import ops  # corte 5
from desk.api.seed_market import seed_market
from desk.api.seed_trades import seed_trades

UI_DIST = Path(__file__).resolve().parents[1] / "ui" / "dist"


def _seed_if_empty(conn) -> None:
    """Siembra solo en el primer arranque (un portafolio vaciado a mano no se resiembra)."""
    if conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 0:
        trades_empty = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        seed_market(conn)
        if trades_empty:
            seed_trades(conn)
        conn.commit()


def create_app(db_path: Optional[Union[str, Path]] = None, seed: bool = True) -> Flask:
    app = Flask(__name__, static_folder=None)
    path = Path(db_path) if db_path is not None else db.DEFAULT_DB_PATH
    app.config["DESK_DB"] = str(path)
    app.config["MDF_DB"] = os.environ.get("MDF_DB") or str(
        Path.home() / "Git" / "MarketDataFeed" / "build" / "sofr.db"
    )
    app.config["MDF_FETCH"] = os.environ.get("MDF_FETCH") or str(
        Path(app.config["MDF_DB"]).parent / "examples" / "fetch_sofr"
    )
    app.config["FRED_DEXMXUS_URL"] = fred.DEXMXUS_URL

    conn = db.connect(path)
    try:
        db.init_schema(conn)
        if seed:
            _seed_if_empty(conn)
    finally:
        conn.close()

    register_error_handlers(app)
    app.teardown_appcontext(db.close_conn)
    for module in (market, price, trades, risk, fixings, pnl, hedges):
        app.register_blueprint(module.bp)
    # --- corte 5 ---
    app.register_blueprint(ops.bp)
    # --- fin corte 5 ---

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path):
        if path == "api" or path.startswith("api/"):
            raise NotFound()
        if not (UI_DIST / "index.html").is_file():
            if path:
                raise NotFound()
            return Response(
                "Interfaz no construida: ejecutar desk/run.sh",
                mimetype="text/plain",
            )
        target = safe_join(str(UI_DIST), path) if path else None
        if target and os.path.isfile(target):
            return send_from_directory(UI_DIST, path)
        return send_from_directory(UI_DIST, "index.html")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5070)
