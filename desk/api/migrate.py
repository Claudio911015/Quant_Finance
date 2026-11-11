"""Migración de la base del corte 1 (`trades` con `params`) al esquema del corte 2.

Es idempotente: solo actúa si `trades` aún tiene la columna `params`. Antes de escribir se
valida cada fila; si una está corrupta aborta con `RuntimeError` que nombra su id y la base
queda intacta. La escritura va en una sola transacción: si algo falla se revierte entera.
"""
import json
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api import db, portfolio
from desk.api.pricing import PRODUCTS
from desk.api.seed_market import SNAPSHOT_ID


def is_v1(conn: sqlite3.Connection) -> bool:
    """True si `trades` existe con el esquema del corte 1 (columna `params`)."""
    return any(row[1] == "params" for row in conn.execute("PRAGMA table_info(trades)"))


def _abort(trade_id: Any, reason: str) -> RuntimeError:
    return RuntimeError("Migración del corte 1 abortada: operación %s: %s" % (trade_id, reason))


def _plan(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones del corte 1 ya validadas y con sus fechas; lanza si alguna no es migrable."""
    row = conn.execute("SELECT as_of FROM snapshots WHERE id = ?", (SNAPSHOT_ID,)).fetchone()
    if row is None:
        raise RuntimeError(
            "Migración del corte 1 abortada: falta el snapshot %s que fecha las operaciones" % SNAPSHOT_ID
        )
    start = date.fromisoformat(row[0])
    plan = []
    for tid, product, counterparty, params_text, created_at in conn.execute(
        "SELECT id, product, counterparty, params, created_at FROM trades ORDER BY id"
    ).fetchall():
        if product not in PRODUCTS:
            raise _abort(tid, "producto desconocido '%s'" % product)
        try:
            raw = json.loads(params_text)
        except (TypeError, ValueError):
            raise _abort(tid, "los parámetros no son JSON legible")
        if not isinstance(raw, dict):
            raise _abort(tid, "los parámetros no son un objeto JSON")
        try:
            params = PRODUCTS[product].validate(raw)
            maturity = portfolio.default_maturity(product, params, start)
        except Exception as e:
            raise _abort(tid, "parámetros inválidos: %s" % e)
        plan.append(
            {
                "id": tid, "product": product, "counterparty": counterparty, "params": params,
                "created_at": created_at, "trade_date": start, "start_date": start,
                "maturity_date": maturity,
            }
        )
    return plan


def migrate_v1(conn: sqlite3.Connection) -> None:
    """Pasa `trades` al esquema nuevo conservando los `id`; cada operación recibe su `execution`."""
    plan = _plan(conn)  # solo lee: si falla, la base no se ha tocado
    try:
        # `executescript` abre la transacción y la deja abierta: el DDL también se revierte.
        conn.executescript(
            "BEGIN IMMEDIATE;\nALTER TABLE trades RENAME TO trades_v1;\n" + db.SCHEMA
        )
        for t in plan:
            portfolio.insert_trade(
                conn, t["product"], t["counterparty"], t["trade_date"], t["start_date"],
                t["maturity_date"], t["params"], t["created_at"], trade_id=t["id"],
            )
        conn.execute("DROP TABLE trades_v1")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
