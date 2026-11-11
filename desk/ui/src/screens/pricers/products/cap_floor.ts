import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'cap_floor',
  title: 'Cap / Floor',
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
      name: 'cap_type',
      label: 'Tipo',
      kind: 'select',
      default: 'cap',
      options: [
        { value: 'cap', label: 'Cap' },
        { value: 'floor', label: 'Floor' },
      ],
    },
    { name: 'notional', label: 'Nocional', kind: 'number', default: 100000000 },
    { name: 'strike', label: 'Tasa strike', kind: 'percent', default: 7.5 },
    {
      name: 'periods',
      label: 'Periodos',
      kind: 'int',
      default: 39,
      help: 'TIIE-F: cupones de 28 días; SOFR: años.',
    },
  ],
  chart: 'payoff',
};
