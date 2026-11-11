"""Mercado: snapshots, curvas y contexto de valuación.

El snapshot vive en SQLite como JSON (`data`); las curvas se arman con
`qfpy.bootstrap_ois` y la superficie con `qfpy.VolSurface`. Aquí no hay fórmulas
financieras: solo se arman objetos de qfpy y se leen sus resultados.
"""
import copy
import json
import re
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional

from desk.api.errors import ApiError
from desk.api.qf import qfpy
from desk.api.validation import MAX_PRICE, finite_number, iso_date, number, text

CURVES = {
    "TIIE-F": {"currency": "MXN", "period_days": 28},
    "SOFR": {"currency": "USD", "period_days": 365},
}

PAIR = "USDMXN"
LIVE_ID = "MKT-LIVE"

# Procedencia de cada componente del snapshot (en el orden del contrato HTTP).
SOURCE_KEYS = (
    "curve:TIIE-F",
    "curve:SOFR",
    "spot",
    "surface",
    "hw",
    "factor_vols",
    "factor_corr",
)
SOURCE_KINDS = ("live", "proxy", "synthetic", "mixed")
_SYNTHETIC_LABEL = "Sintético (inventado para demostración)"
DEFAULT_SOURCES = {
    key: {"kind": "synthetic", "label": _SYNTHETIC_LABEL, "as_of": None}
    for key in SOURCE_KEYS
}
_RATE_MIN = -0.05  # exclusivo
_RATE_MAX = 1.0  # exclusivo

# --- corte 3 ---
CSA_CURVE = "MXN-USD"  # descuento MXN bajo colateral USD; NO entra a CURVES (curvas elegibles por los pricers)
CSA_PERIOD_DAYS = 28
CSA_SOURCE = {"kind": "synthetic", "label": _SYNTHETIC_LABEL, "as_of": None}
CSA_UNAVAILABLE_MESSAGE = (
    "El snapshot no trae puntos forward ni base de cross currency swaps: "
    "la curva MXN-USD no existe y todo se descuenta con TIIE-F"
)
_MAX_LABEL = 40


def _quote_list(data: Dict[str, Any], key: str, value_key: str, what: str) -> List[Dict[str, Any]]:
    """Normaliza `data[key]` a `[{"days": int, value_key: float, "label": str}]`.

    Ausente o `None` es lista vacía. `days` enteros > 0 estrictamente crecientes, valor finito y
    `label` opcional (por omisión `"<días>d"`); cualquier otra cosa es `RuntimeError` en español.
    """
    raw = data.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RuntimeError("'%s' del snapshot debe ser una lista de %s" % (key, what))
    out = []
    previous = 0
    for i, item in enumerate(raw):
        where = "%s[%d]" % (key, i)
        if not isinstance(item, dict):
            raise RuntimeError("%s del snapshot debe ser un objeto" % where)
        days = item.get("days")
        if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise RuntimeError("%s del snapshot: 'days' debe ser un entero mayor que 0" % where)
        if days <= previous:
            raise RuntimeError("%s del snapshot: los 'days' deben ir en orden estrictamente creciente" % key)
        value = item.get(value_key)
        if not finite_number(value):
            raise RuntimeError("%s del snapshot: '%s' debe ser un número finito" % (where, value_key))
        label = item.get("label")
        if label is None:
            label = "%dd" % days
        elif not isinstance(label, str) or not label.strip() or len(label) > _MAX_LABEL:
            raise RuntimeError(
                "%s del snapshot: 'label' debe ser un texto de 1 a %d caracteres" % (where, _MAX_LABEL)
            )
        out.append({"days": days, value_key: float(value), "label": label})
        previous = days
    return out


def normalize_csa_quotes(data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """`{"fx_forwards": [...], "xccy_basis": [...]}` normalizados (listas vacías si faltan).

    Los puntos forward van antes que la base: la primera base debe caer después del último forward.
    """
    forwards = _quote_list(data, "fx_forwards", "points", "puntos forward")
    basis = _quote_list(data, "xccy_basis", "spread", "cotizaciones de base")
    if forwards and basis and basis[0]["days"] <= forwards[-1]["days"]:
        raise RuntimeError(
            "xccy_basis del snapshot: la primera base (%d días) debe caer después del último punto forward (%d días)"
            % (basis[0]["days"], forwards[-1]["days"])
        )
    return {"fx_forwards": forwards, "xccy_basis": basis}


def _calibrate_csa(
    csa_quotes: Dict[str, List[Dict[str, Any]]], spot: float, curves: Dict[str, "qfpy.YieldCurve"]
) -> "qfpy.YieldCurve":
    """`MXN-USD` con las cotizaciones fijas sobre `curves["SOFR"]`, `curves["TIIE-F"]` y `spot`."""
    try:
        curve = qfpy.bootstrap_xccy_discount(
            [qfpy.FxForwardQuote(q["days"], q["points"]) for q in csa_quotes["fx_forwards"]],
            [qfpy.XccyBasisQuote(q["days"], q["spread"]) for q in csa_quotes["xccy_basis"]],
            spot,
            curves["SOFR"],
            curves["TIIE-F"],
            CSA_PERIOD_DAYS,
        )
    except Exception as e:  # frontera con C++: ValueError, RuntimeError o TypeError de pybind
        raise RuntimeError("No se pudo calibrar la curva %s: %s" % (CSA_CURVE, e))
    if len(curve.maturities()) != len(csa_quotes["fx_forwards"]) + len(csa_quotes["xccy_basis"]):
        raise RuntimeError("la curva %s no tiene un pilar por cotización" % CSA_CURVE)
    return curve


def _shift_curve(
    curve: "qfpy.YieldCurve",
    pillars: List[Dict[str, Any]],
    name: str,
    pillar_shifts_bp: Optional[List[float]],
    parallel_bp: Optional[float],
) -> "qfpy.YieldCurve":
    """`curve` con los desplazamientos por pilar y/o paralelo (pb de tasa cero)."""
    if pillar_shifts_bp is not None:
        if len(pillar_shifts_bp) != len(pillars):
            raise ValueError("se esperaban %d desplazamientos para %s" % (len(pillars), name))
        for i, bp in enumerate(pillar_shifts_bp):
            if bp:
                curve = curve.bumped(i, float(bp))
    if parallel_bp is not None:
        curve = curve.parallel_bump(float(parallel_bp))
    return curve
# --- fin corte 3 ---


class MarketContext:
    """Estado de mercado listo para valuar.

    Atributos: snapshot_id, as_of (date), curves (Dict[str, qfpy.YieldCurve]),
    pillars (Dict[str, List[dict]] con "label" y "days", alineados con los pilares
    de la curva), spot (float), surface (qfpy.VolSurface), hw (dict), factors (dict),
    env (qfpy.MarketEnvironment con curvas "TIIE-F" y "SOFR", spot y superficie "USDMXN").

    Corte 3: con `csa_quotes` (puntos forward y base ya normalizados) el constructor calibra la curva
    `MXN-USD` (descuento MXN bajo colateral USD) y la agrega a `curves`, `pillars` y `env`. Atributos
    del colateral: `csa_available`, `collateral`, `mxn_discount`, `csa_missing` (ver `with_collateral`).
    """

    def __init__(
        self,
        snapshot_id: str,
        as_of: date,
        curves: Dict[str, "qfpy.YieldCurve"],
        pillars: Dict[str, List[Dict[str, Any]]],
        spot: float,
        surface: "qfpy.VolSurface",
        hw: Dict[str, Any],
        factors: Dict[str, Any],
        csa_quotes: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        self.snapshot_id = snapshot_id
        self.as_of = as_of
        self.curves = dict(curves)
        self.pillars = dict(pillars)
        self.spot = spot
        self.surface = surface
        self.hw = hw
        self.factors = factors
        # --- corte 3 ---
        self.csa_quotes = csa_quotes
        if csa_quotes is not None:
            if CSA_CURVE not in self.curves:  # `shifted` la trae ya recalibrada o desplazada
                self.curves[CSA_CURVE] = _calibrate_csa(csa_quotes, spot, self.curves)
            self.pillars[CSA_CURVE] = [
                {"label": q["label"], "days": q["days"]}
                for q in csa_quotes["fx_forwards"] + csa_quotes["xccy_basis"]
            ]
        self.csa_available = CSA_CURVE in self.curves
        self.collateral = "MXN"
        self.mxn_discount = "TIIE-F"
        self.csa_missing = False
        # --- fin corte 3 ---
        self.env = self._make_env()

    # --- corte 3 ---
    def curve_names(self) -> List[str]:
        """Curvas de este contexto: `["TIIE-F", "SOFR"]` y, si existe, `"MXN-USD"`."""
        return list(CURVES) + ([CSA_CURVE] if self.csa_available else [])

    def with_collateral(self, currency: str) -> "MarketContext":
        """Copia (mismas curvas, sin recalibrar) con el colateral `currency` ("MXN" o "USD").

        `mxn_discount` es `"MXN-USD"` solo con colateral USD y curva disponible; con colateral USD y
        sin curva queda `"TIIE-F"` y `csa_missing = True`.
        """
        if currency not in ("MXN", "USD"):
            raise ValueError("moneda de colateral desconocida: %s" % currency)
        out = copy.copy(self)
        out.collateral = currency
        out.mxn_discount = CSA_CURVE if currency == "USD" and self.csa_available else "TIIE-F"
        out.csa_missing = currency == "USD" and not self.csa_available
        return out
    # --- fin corte 3 ---

    def _make_env(self, default_curve: Optional[str] = None) -> "qfpy.MarketEnvironment":
        env = qfpy.MarketEnvironment()
        for name, curve in self.curves.items():
            env.add_curve(name, curve)
        if default_curve is not None:
            env.add_curve("default", self.curves[default_curve])
        env.set_spot(PAIR, self.spot)
        env.set_vol_surface(PAIR, self.surface)
        return env

    def env_with_default(self, curve: str) -> "qfpy.MarketEnvironment":
        """`env` más la curva "default" apuntando a `curve`."""
        if curve not in self.curves:
            raise ValueError("curva desconocida: %s" % curve)
        return self._make_env(default_curve=curve)

    def shifted(
        self,
        curve: Optional[str] = None,
        pillar_shifts_bp: Optional[List[float]] = None,
        parallel_bp: Optional[float] = None,
        spot_pct: float = 0.0,
    ) -> "MarketContext":
        """Copia con la curva desplazada y/o el spot × (1 + spot_pct/100).

        `pillar_shifts_bp` lleva un desplazamiento (pb de tasa cero) por pilar de `curve`,
        en el orden de `pillars[curve]`; `parallel_bp` desplaza todos los pilares. Ambos
        pueden combinarse. El contexto original no cambia.

        Curva dependiente (corte 3): un choque a TIIE-F, SOFR o al spot recalibra `MXN-USD` con sus
        cotizaciones fijas sobre las curvas/spot ya chocados; un choque a `MXN-USD` desplaza solo sus
        pilares (sobre la recalibrada si además hay `spot_pct`). Conserva el colateral.
        """
        curves = dict(self.curves)
        spot = self.spot * (1.0 + spot_pct / 100.0)
        wants_shift = pillar_shifts_bp is not None or parallel_bp is not None
        if wants_shift:
            if curve not in self.curves:
                raise ValueError("curva desconocida: %s" % curve)
            if curve != CSA_CURVE:
                curves[curve] = _shift_curve(
                    self.curves[curve], self.pillars[curve], curve, pillar_shifts_bp, parallel_bp
                )
        # --- corte 3 ---
        if self.csa_quotes is not None:
            if spot != self.spot or (wants_shift and curve != CSA_CURVE):
                curves[CSA_CURVE] = _calibrate_csa(self.csa_quotes, spot, curves)
            if wants_shift and curve == CSA_CURVE:
                curves[CSA_CURVE] = _shift_curve(
                    curves[CSA_CURVE], self.pillars[CSA_CURVE], CSA_CURVE, pillar_shifts_bp, parallel_bp
                )
        # --- fin corte 3 ---
        out = MarketContext(
            self.snapshot_id,
            self.as_of,
            curves,
            self.pillars,
            spot,
            self.surface,
            self.hw,
            self.factors,
            self.csa_quotes,
        )
        out.collateral = self.collateral
        out.mxn_discount = self.mxn_discount
        out.csa_missing = self.csa_missing
        return out


def _not_found(snapshot_id: str) -> ApiError:
    return ApiError(404, "Snapshot no encontrado: %s" % snapshot_id, "snapshot")


def _fetch(conn: sqlite3.Connection, snapshot_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, label, synthetic, as_of, data FROM snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise _not_found(snapshot_id)
    return row


def _build_context(snapshot_id: str, as_of: str, data: Dict[str, Any]) -> MarketContext:
    curves = {}  # type: Dict[str, Any]
    pillars = {}  # type: Dict[str, List[Dict[str, Any]]]
    for name, spec in CURVES.items():
        quotes = [q for q in data["quotes"] if q["curve"] == name]
        pillars[name] = [{"label": q["label"], "days": q["days"]} for q in quotes]
        ois_type = qfpy.OisQuoteType
        curves[name] = qfpy.bootstrap_ois(
            [
                qfpy.OisQuote(
                    q["days"],
                    q["rate"],
                    ois_type.Deposit if q["type"] == "deposit" else ois_type.Ois,
                )
                for q in quotes
            ],
            spec["period_days"],
        )
        if len(curves[name].maturities()) != len(quotes):
            raise RuntimeError("la curva %s no tiene un pilar por cotización" % name)
    vol = data["vol_surface"]
    surface = qfpy.VolSurface(
        [d / 365.0 for d in vol["expiry_days"]], vol["strikes"], vol["vols"]
    )
    # --- corte 3 ---
    csa_quotes = normalize_csa_quotes(data)
    if len(csa_quotes["fx_forwards"]) + len(csa_quotes["xccy_basis"]) < 2:
        csa_quotes = None  # sin cotizaciones suficientes no hay curva MXN-USD
    # --- fin corte 3 ---
    return MarketContext(
        snapshot_id,
        date.fromisoformat(as_of),
        curves,
        pillars,
        float(data["fx"]["spot"]),
        surface,
        data["hw"],
        data["factors"],
        csa_quotes,
    )


def load_context(conn: sqlite3.Connection, snapshot_id: str) -> MarketContext:
    """Contexto del snapshot; 404 `field: "snapshot"` si no existe."""
    row = _fetch(conn, snapshot_id)
    return _build_context(row["id"], row["as_of"], json.loads(row["data"]))


def sources_of(data: Dict[str, Any]) -> Dict[str, Any]:
    """Procedencia guardada en `data["sources"]`; sin ella, todo sintético."""
    return data.get("sources") or DEFAULT_SOURCES


def data_quality(sources: Dict[str, Any]) -> str:
    """"synthetic" si todo es sintético, "live" si nada es sintético ni mixto, si no "mixed"."""
    kinds = [s["kind"] for s in sources.values()]
    if all(k == "synthetic" for k in kinds):
        return "synthetic"
    if not any(k in ("synthetic", "mixed") for k in kinds):
        return "live"
    return "mixed"


def list_snapshots(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Resumen `{"id","label","synthetic","as_of","data_quality","sources"}` de cada snapshot."""
    rows = conn.execute(
        "SELECT id, label, synthetic, as_of, data FROM snapshots ORDER BY id"
    ).fetchall()
    out = []
    for r in rows:
        sources = sources_of(json.loads(r["data"]))
        out.append(
            {
                "id": r["id"],
                "label": r["label"],
                "synthetic": bool(r["synthetic"]),
                "as_of": r["as_of"],
                "data_quality": data_quality(sources),
                "sources": sources,
            }
        )
    return out


def _curve_points(ctx: MarketContext, name: str) -> List[Dict[str, Any]]:
    curve = ctx.curves[name]
    points = []
    t_prev = 0.0
    for p in ctx.pillars[name]:
        t = p["days"] / 365.0
        points.append(
            {
                "label": p["label"],
                "days": p["days"],
                "t": t,
                "zero": curve.zero_rate(t),
                "df": curve.discount_factor(t),
                "forward": curve.forward_rate(t_prev, t),
            }
        )
        t_prev = t
    return points


def _curves_payload(ctx: MarketContext) -> Dict[str, Any]:
    out = {
        name: {
            "currency": spec["currency"],
            "period_days": spec["period_days"],
            "points": _curve_points(ctx, name),
        }
        for name, spec in CURVES.items()
    }
    # --- corte 3 ---
    if ctx.csa_available:
        out[CSA_CURVE] = {
            "currency": "MXN",
            "period_days": CSA_PERIOD_DAYS,
            "dependent": True,
            "points": _curve_points(ctx, CSA_CURVE),
        }
    # --- fin corte 3 ---
    return out


# --- corte 3 ---
def _csa_info(data: Dict[str, Any], ctx: MarketContext) -> Dict[str, Any]:
    """Bloque `csa` del payload: procedencia y forward implícito vs cotizado (sin curva: no disponible)."""
    if not ctx.csa_available:
        return {
            "available": False,
            "curve": CSA_CURVE,
            "source": None,
            "message": CSA_UNAVAILABLE_MESSAGE,
            "implied_vs_quoted": [],
        }
    source = data.get("csa_source")
    rows = []
    for q in ctx.csa_quotes["fx_forwards"]:
        implied = qfpy.FxForward(1.0, 1.0, q["days"], qfpy.FxSide.Buy, PAIR, CSA_CURVE).forward_rate(ctx.env)
        parity = qfpy.FxForward(1.0, 1.0, q["days"], qfpy.FxSide.Buy, PAIR, "TIIE-F").forward_rate(ctx.env)
        quoted = ctx.spot + q["points"]
        rows.append(
            {
                "label": q["label"],
                "days": q["days"],
                "quoted_points": q["points"],
                "quoted_forward": quoted,
                "implied_forward": implied,
                "parity_forward": parity,
                "diff": implied - quoted,
            }
        )
    return {
        "available": True,
        "curve": CSA_CURVE,
        "source": source if isinstance(source, dict) else dict(CSA_SOURCE),
        "message": None,
        "implied_vs_quoted": rows,
    }


# --- fin corte 3 ---
def _payload(row: sqlite3.Row, data: Dict[str, Any], ctx: MarketContext) -> Dict[str, Any]:
    sources = sources_of(data)
    csa_quotes = normalize_csa_quotes(data)  # ya validadas al construir `ctx`
    return {
        "id": row["id"],
        "label": row["label"],
        "synthetic": bool(row["synthetic"]),
        "as_of": row["as_of"],
        "data_quality": data_quality(sources),
        "sources": sources,
        "read_only": row["id"] == LIVE_ID,
        "quotes": data["quotes"],
        "curves": _curves_payload(ctx),
        "fx": data["fx"],
        "vol_surface": data["vol_surface"],
        "hw": data["hw"],
        "factors": data["factors"],
        # --- corte 3 ---
        "fx_forwards": csa_quotes["fx_forwards"] or None,
        "xccy_basis": csa_quotes["xccy_basis"] or None,
        "csa": _csa_info(data, ctx),
        # --- fin corte 3 ---
    }


def snapshot_payload(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo completo de `GET /api/market/snapshots/<id>`; 404 `field: "snapshot"` si no existe."""
    row = _fetch(conn, snapshot_id)
    data = json.loads(row["data"])
    return _payload(row, data, _build_context(row["id"], row["as_of"], data))


def _quote_rate(item: Any, known: Dict[str, Dict[str, Any]]) -> Any:
    """Valida un elemento de `quotes` y devuelve `(cotización, tasa)`."""
    if not isinstance(item, dict):
        raise ApiError(400, "Cada elemento de 'quotes' debe ser un objeto", "quotes")
    qid = item.get("id")
    if not isinstance(qid, str) or qid not in known:
        raise ApiError(400, "Cotización desconocida: %s" % (qid,), "quotes")
    rate = item.get("rate")
    if not finite_number(rate):
        raise ApiError(400, "La tasa de %s debe ser un número" % qid, "quotes")
    if not _RATE_MIN < rate < _RATE_MAX:
        raise ApiError(
            400,
            "La tasa de %s debe estar entre %s y %s (decimal)" % (qid, _RATE_MIN, _RATE_MAX),
            "quotes",
        )
    return known[qid], float(rate)


def update_snapshot(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Valida y persiste `quotes`/`spot` del cuerpo; devuelve el payload recalculado."""
    row = _fetch(conn, snapshot_id)
    if snapshot_id == LIVE_ID:
        raise ApiError(
            409, "Mercado vivo se reconstruye en cada actualización; no se edita", None
        )
    data = json.loads(row["data"])

    new_quotes = body.get("quotes")
    has_spot = body.get("spot") is not None
    if new_quotes is None and not has_spot:
        raise ApiError(400, "Se requiere 'quotes' o 'spot'")

    changes = []
    if new_quotes is not None:
        if not isinstance(new_quotes, list) or not new_quotes:
            raise ApiError(400, "'quotes' debe ser una lista no vacía", "quotes")
        known = {q["id"]: q for q in data["quotes"]}
        changes = [_quote_rate(item, known) for item in new_quotes]
    spot = number(body, "spot", gt=0, le=MAX_PRICE) if has_spot else None

    for quote, rate in changes:
        quote["rate"] = rate
    if spot is not None:
        data["fx"]["spot"] = spot

    ctx = _build_context(row["id"], row["as_of"], data)  # falla antes de persistir
    conn.execute(
        "UPDATE snapshots SET data = ? WHERE id = ?", (json.dumps(data), snapshot_id)
    )
    return _payload(row, data, ctx)


_ROLL_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
_ROLLED_SUFFIX = re.compile(r" · rodado al \d{4}-\d{2}-\d{2}$")


def roll_snapshot(conn: sqlite3.Connection, source_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Copia el snapshot `source_id` con otro `id` y `as_of` (`body`); devuelve el payload del nuevo.

    El rótulo es el del origen más ` · rodado al <as_of>`; si el origen ya lo traía, se reemplaza en
    vez de encadenarse. La copia es editable aunque el origen sea `MKT-LIVE`. Errores: 400 `id`/`as_of`,
    404 `snapshot` si el origen no existe, 409 `id` si el nuevo ya existe.
    """
    new_id = text(body, "id")
    if new_id != body["id"] or new_id == LIVE_ID or not _ROLL_ID.fullmatch(new_id):
        raise ApiError(
            400,
            "El id debe tener de 1 a 40 caracteres: letras, dígitos, '_' o '-' (MKT-LIVE está reservado)",
            "id",
        )
    as_of = iso_date(body, "as_of").isoformat()
    row = _fetch(conn, source_id)
    if conn.execute("SELECT 1 FROM snapshots WHERE id = ?", (new_id,)).fetchone():
        raise ApiError(409, "Ya existe un snapshot con id %s" % new_id, "id")
    conn.execute(
        "INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES (?, ?, ?, ?, ?)",
        (
            new_id,
            "%s · rodado al %s" % (_ROLLED_SUFFIX.sub("", row["label"]), as_of),
            row["synthetic"],
            as_of,
            row["data"],
        ),
    )
    return snapshot_payload(conn, new_id)
