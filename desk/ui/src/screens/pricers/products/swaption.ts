import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'swaption',
  title: 'Swaption',
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
      name: 'swaption_type',
      label: 'Tipo',
      kind: 'select',
      default: 'payer',
      options: [
        { value: 'payer', label: 'Pagador de fija' },
        { value: 'receiver', label: 'Receptor de fija' },
      ],
    },
    { name: 'notional', label: 'Nocional', kind: 'number', default: 100000000 },
    { name: 'strike', label: 'Tasa strike', kind: 'percent', default: 7 },
    { name: 'expiry_years', label: 'Vencimiento (años)', kind: 'number', default: 1 },
    { name: 'swap_tenor_years', label: 'Plazo del swap (años)', kind: 'number', default: 5 },
  ],
  chart: 'none',
};
