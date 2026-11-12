import type { ProductSpec } from '../types';
import { exoticFields } from './fx_no_touch';

export const spec: ProductSpec = {
  product: 'fx_double_no_touch',
  title: 'Double no touch USDMXN',
  fields: exoticFields([
    { name: 'lower', label: 'Barrera inferior', kind: 'number', default: 17.5 },
    { name: 'upper', label: 'Barrera superior', kind: 'number', default: 19.8 },
  ]),
  chart: 'payoff',
};
