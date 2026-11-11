"""Tipo común de los pricers del desk."""
from collections import namedtuple

# validate(params) -> dict normalizado, o ApiError(400, ..., field)
# price(params, mkt) -> cuerpo de respuesta de /api/price (params ya normalizados)
# pv_mxn(params, mkt) -> float, PV en MXN (USD × mkt.spot)
# describe(params, as_of) -> {"notional", "currency", "maturity"}
Product = namedtuple("Product", "name validate price pv_mxn describe")
