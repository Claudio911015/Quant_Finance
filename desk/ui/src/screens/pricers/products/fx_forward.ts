import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'fx_forward',
  title: 'Forward FX',
  fields: [
    {
      name: 'side',
      label: 'Posición',
      kind: 'select',
      default: 'buy',
      options: [
        { value: 'buy', label: 'Compra de USD' },
        { value: 'sell', label: 'Venta de USD' },
      ],
    },
    { name: 'notional_usd', label: 'Nocional (USD)', kind: 'number', default: 1000000 },
    {
      name: 'strike',
      label: 'Precio pactado',
      kind: 'number',
      default: '18.90',
      help: 'MXN por USD.',
    },
    { name: 'days', label: 'Días al vencimiento', kind: 'int', default: 91 },
  ],
  chart: 'payoff',
};
