import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'fx_option',
  title: 'Opción FX',
  fields: [
    {
      name: 'side',
      label: 'Posición',
      kind: 'select',
      default: 'buy',
      options: [
        { value: 'buy', label: 'Compra' },
        { value: 'sell', label: 'Venta' },
      ],
    },
    {
      name: 'option_type',
      label: 'Tipo',
      kind: 'select',
      default: 'call',
      options: [
        { value: 'call', label: 'Call sobre USD' },
        { value: 'put', label: 'Put sobre USD' },
      ],
    },
    { name: 'notional_usd', label: 'Nocional (USD)', kind: 'number', default: 1000000 },
    {
      name: 'strike',
      label: 'Strike',
      kind: 'number',
      default: 19,
      help: 'MXN por USD.',
    },
    { name: 'days', label: 'Días al vencimiento', kind: 'int', default: 91 },
  ],
  chart: 'payoff',
};
