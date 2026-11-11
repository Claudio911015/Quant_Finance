from typing import Dict

from desk.api.pricing import fx, rates, xccy
from desk.api.pricing.base import Product

PRODUCTS: Dict[str, Product] = {**rates.PRODUCTS, **fx.PRODUCTS, **xccy.PRODUCTS}

# Rótulo en español de cada producto: el mismo que muestra la interfaz (`screens/pricers/products/*`).
# Los avisos y errores de la API lo usan en lugar del código interno.
PRODUCT_LABEL: Dict[str, str] = {
    "irs": "Swap de tasas (IRS)",
    "fx_forward": "Forward FX",
    "fx_option": "Opción FX",
    "cap_floor": "Cap / Floor",
    "equity_option": "Opción sobre acción",
    "swaption": "Swaption",
    "bond": "Bono",
    "xccy_swap": "Cross currency swap USDMXN",
}
