import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'bond',
  title: 'Bono',
  fields: [
    {
      name: 'curve',
      label: 'Curva',
      kind: 'select',
      default: 'TIIE-F',
      options: [
        { value: 'TIIE-F', label: 'TIIE-F (MXN)' },
        { value: 'SOFR', label: 'SOFR (USD)' },
      ],
    },
    { name: 'face', label: 'Valor nominal', kind: 'number', default: 100 },
    { name: 'coupon_rate', label: 'Cupón', kind: 'percent', default: 8 },
    {
      name: 'periods',
      label: 'Periodos',
      kind: 'int',
      default: 20,
      help: 'Número de cupones.',
    },
    {
      name: 'frequency',
      label: 'Frecuencia',
      kind: 'int',
      default: 2,
      help: 'Cupones por año.',
    },
  ],
  chart: 'cashflows',
};
