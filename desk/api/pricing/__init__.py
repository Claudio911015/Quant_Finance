from collections import ChainMap
from typing import Dict

from desk.api.pricing import fx, fx_exotics, rates, xccy
from desk.api.pricing.base import Product

PRODUCTS: Dict[str, Product] = {**rates.PRODUCTS, **fx.PRODUCTS, **xccy.PRODUCTS}
# Solo la ruta de precios los ve: los exóticos no entran al portafolio (PRODUCTS lo usan create_trade, valuación y ciclo de vida).
PRICERS = ChainMap(PRODUCTS, fx_exotics.PRODUCTS)  # vista viva: lo que se parchee en PRODUCTS lo ve la ruta

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
    "fx_no_touch": "No touch USDMXN",
    "fx_double_no_touch": "Double no touch USDMXN",
}
