import { EXCHANGE_LABEL, XCCY_SIDE_LABEL } from '../../../lib/csaLabels';
import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'xccy_swap',
  title: 'Cross currency swap USDMXN',
  fields: [
    {
      name: 'side',
      label: 'Posición',
      kind: 'select',
      default: 'pay_usd',
      options: [
        { value: 'pay_usd', label: XCCY_SIDE_LABEL.pay_usd },
        { value: 'pay_mxn', label: XCCY_SIDE_LABEL.pay_mxn },
      ],
    },
    { name: 'notional_usd', label: 'Nocional USD', kind: 'number', default: 10000000 },
    {
      name: 'periods',
      label: 'Periodos',
      kind: 'int',
      default: 26,
      help: 'Cupones de 28 días en ambas patas',
    },
    {
      name: 'fx_rate',
      label: 'Tipo de cambio inicial',
      kind: 'number',
      default: null,
      optional: true,
      help: 'Vacío = spot',
    },
    {
      name: 'spread',
      label: 'Diferencial sobre TIIE-F',
      kind: 'percent',
      default: null,
      optional: true,
      help: 'Vacío = diferencial par',
    },
    {
      name: 'exchange',
      label: 'Intercambio de nocional',
      kind: 'select',
      default: 'both',
      options: [
        { value: 'both', label: EXCHANGE_LABEL.both },
        { value: 'initial', label: EXCHANGE_LABEL.initial },
        { value: 'final', label: EXCHANGE_LABEL.final },
        { value: 'none', label: EXCHANGE_LABEL.none },
      ],
    },
  ],
  chart: 'cashflows',
};
