import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'irs',
  title: 'Swap de tasas (IRS)',
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
    {
      name: 'side',
      label: 'Posición',
      kind: 'select',
      default: 'payer',
      options: [
        { value: 'payer', label: 'Pagador de fija' },
        { value: 'receiver', label: 'Receptor de fija' },
      ],
    },
    { name: 'notional', label: 'Nocional', kind: 'number', default: 100000000 },
    {
      name: 'periods',
      label: 'Periodos',
      kind: 'int',
      default: 13,
      help: 'TIIE-F: cupones de 28 días; SOFR: años.',
    },
    {
      name: 'fixed_rate',
      label: 'Tasa fija',
      kind: 'percent',
      default: null,
      optional: true,
      help: 'Vacía = tasa par.',
    },
  ],
  chart: 'cashflows',
};
