import type { FieldSpec, ProductSpec } from '../types';

/** Campos de los dos exóticos de FX: la posición, las barreras de cada producto y el resto, comunes. */
export const exoticFields = (barriers: FieldSpec[]): FieldSpec[] => [
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
  ...barriers,
  { name: 'payout_mxn', label: 'Pago (MXN)', kind: 'number', default: 1000000 },
  { name: 'days', label: 'Días al vencimiento', kind: 'int', default: 91 },
  {
    name: 'model',
    label: 'Modelo',
    kind: 'select',
    default: 'smile',
    options: [
      { value: 'smile', label: 'Con sonrisa (vol local)' },
      { value: 'flat', label: 'Plano' },
    ],
  },
  {
    name: 'method',
    label: 'Método',
    kind: 'select',
    default: 'mc',
    options: [
      { value: 'mc', label: 'Monte Carlo' },
      { value: 'analytic', label: 'Analítico (solo plano)' },
    ],
  },
];

export const spec: ProductSpec = {
  product: 'fx_no_touch',
  title: 'No touch USDMXN',
  fields: exoticFields([
    { name: 'barrier', label: 'Barrera', kind: 'number', default: 19.5 },
    {
      name: 'barrier_type',
      label: 'Tipo de barrera',
      kind: 'select',
      default: 'up',
      options: [
        { value: 'up', label: 'Arriba' },
        { value: 'down', label: 'Abajo' },
      ],
    },
  ]),
  chart: 'payoff',
};
