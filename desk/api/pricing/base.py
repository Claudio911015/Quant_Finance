"""Tipo común de los pricers del desk."""
from collections import namedtuple

# validate(params) -> dict normalizado, o ApiError(400, ..., field)
# price(params, mkt) -> cuerpo de respuesta de /api/price (params ya normalizados)
# pv_mxn(params, mkt) -> float, PV en MXN (USD × mkt.spot)
# describe(params, as_of) -> {"notional", "currency", "maturity"}
Product = namedtuple("Product", "name validate price pv_mxn describe")

# Cotas de entrada de los pricers (inclusivas): fuera de ellas la valuación es inviable o
# desborda el calendario, así que se rechazan en `validate` con 400 y el campo culpable.
MAX_PERIODS = 1200  # periodos de swaps, caps/floors y bonos
MAX_DAYS = 18250  # días al vencimiento de forwards y opciones FX (50 años)
MAX_YEARS = 50  # años de vencimiento de swaptions y opciones sobre acción
MAX_BOND_YEARS = 1200  # vida del bono = periods / frequency; más allá desborda el calendario
