from typing import Dict

from desk.api.pricing import fx, rates, xccy
from desk.api.pricing.base import Product

PRODUCTS: Dict[str, Product] = {**rates.PRODUCTS, **fx.PRODUCTS, **xccy.PRODUCTS}
