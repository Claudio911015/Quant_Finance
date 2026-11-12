import type { ProductId } from '../../api/types';
import type { ProductSpec } from './types';
import { spec as irs } from './products/irs';
import { spec as fx_forward } from './products/fx_forward';
import { spec as fx_option } from './products/fx_option';
import { spec as cap_floor } from './products/cap_floor';
import { spec as swaption } from './products/swaption';
import { spec as bond } from './products/bond';
import { spec as equity_option } from './products/equity_option';
import { spec as xccy_swap } from './products/xccy_swap';
import { spec as fx_no_touch } from './products/fx_no_touch';
import { spec as fx_double_no_touch } from './products/fx_double_no_touch';

export const PRODUCT_SPECS: Record<ProductId, ProductSpec> = {
  irs,
  fx_forward,
  fx_option,
  cap_floor,
  swaption,
  bond,
  equity_option,
  xccy_swap,
  fx_no_touch,
  fx_double_no_touch,
};

/** Rótulo en español de un producto (el de Pricers); un id desconocido o una fila especial se muestran tal cual. */
export function productTitle(product: string): string {
  return (PRODUCT_SPECS as Record<string, ProductSpec | undefined>)[product]?.title ?? product;
}
