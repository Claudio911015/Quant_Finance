"""Refresco de `MKT-LIVE`: ejecutable de MarketDataFeed, descarga de FRED y reconstrucción.

Un solo refresco a la vez (candado de proceso). Todo fallo posterior a la decisión de ejecutar
es 502 con el motivo y deja `MKT-LIVE` como estaba; el único 409 es "ya hay un refresco en curso".
"""
import http.client
import subprocess
import threading
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from desk.api import fred, live_market, market
from desk.api.errors import ApiError

FETCH_TIMEOUT_S = 120
STDERR_TAIL = 300
_LOCK = threading.Lock()


def _run_fetch(fetch: str, mdf_db: str) -> int:
    """Ejecuta `fetch_sofr --latest --treasury --db <mdf_db>` (sin shell); 502 si no sale con 0."""
    cmd = [fetch, "--latest", "--treasury", "--db", mdf_db]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=FETCH_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise ApiError(
            502, "MarketDataFeed no terminó en %d s (%s)" % (FETCH_TIMEOUT_S, fetch)
        )
    except OSError as e:
        raise ApiError(502, "No se pudo ejecutar MarketDataFeed (%s): %s" % (fetch, e))
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", errors="replace").strip()[-STDERR_TAIL:]
        raise ApiError(
            502,
            "MarketDataFeed terminó con código %d%s"
            % (proc.returncode, (": " + tail) if tail else ""),
        )
    return proc.returncode


def _why(e: BaseException) -> str:
    """Motivo legible de un fallo de red o de formato de FRED."""
    if isinstance(e, urllib.error.URLError) and not isinstance(e, urllib.error.HTTPError):
        return str(e.reason)
    return str(e) or type(e).__name__


def _fetch_fx(url: str):
    try:
        return fred.fetch_dexmxus(url)
    except (OSError, ValueError, http.client.HTTPException) as e:  # URLError y timeout son OSError
        raise ApiError(502, "FRED no respondió: %s" % _why(e))


def _refresh(conn, config: Mapping[str, Any]) -> Dict[str, Any]:
    mdf_db = str(config["MDF_DB"])
    exit_code = _run_fetch(str(config["MDF_FETCH"]), mdf_db)
    fx_series = _fetch_fx(config["FRED_DEXMXUS_URL"])
    try:
        info = live_market.rebuild_live(conn, mdf_db, fx_series)
        snapshot = market.snapshot_payload(conn, market.LIVE_ID)
        conn.commit()
    except ApiError as e:  # lectura de MarketDataFeed o historia insuficiente: 409 fuera, 502 aquí
        conn.rollback()
        raise ApiError(502, e.error)
    except Exception as e:  # bootstrap, datos no finitos, base de escritura
        conn.rollback()
        raise ApiError(502, "No se pudo construir Mercado vivo: %s" % e)
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mdf_exit_code": exit_code,
        "treasury_latest": info["treasury_latest"],
        "sofr_latest": info["sofr_latest"],
        "fred_latest": info["fred_latest"],
        "snapshot": snapshot,
    }


def run_refresh(conn, config: Mapping[str, Any]) -> Dict[str, Any]:
    """Refresca `MKT-LIVE` y devuelve el cuerpo de `POST /api/market/refresh`."""
    if not _LOCK.acquire(blocking=False):
        raise ApiError(409, "Ya hay una actualización de datos en curso")
    try:
        return _refresh(conn, config)
    finally:
        _LOCK.release()
