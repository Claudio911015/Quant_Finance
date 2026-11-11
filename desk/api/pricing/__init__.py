from typing import Dict

from desk.api.pricing import fx, rates
from desk.api.pricing.base import Product

PRODUCTS: Dict[str, Product] = {**rates.PRODUCTS, **fx.PRODUCTS}
