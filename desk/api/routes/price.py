from flask import Blueprint, jsonify

from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.market import load_context
from desk.api.pricing import PRODUCTS
from desk.api.validation import body_object, text

bp = Blueprint("price", __name__, url_prefix="/api/price")


@bp.post("/<product>")
def price(product):
    if product not in PRODUCTS:
        raise ApiError(404, "Producto desconocido: %s" % product, "product")
    body = body_object()
    snapshot_id = text(body, "snapshot")
    params = PRODUCTS[product].validate(
        {k: v for k, v in body.items() if k != "snapshot"}
    )
    mkt = load_context(get_conn(), snapshot_id)
    return jsonify(PRODUCTS[product].price(params, mkt))
