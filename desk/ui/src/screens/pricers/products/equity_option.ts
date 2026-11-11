import type { ProductSpec } from '../types';

export const spec: ProductSpec = {
  product: 'equity_option',
  title: 'Opción sobre acción',
  fields: [
    {
      name: 'option_type',
      label: 'Tipo',
      kind: 'select',
      default: 'call',
      options: [
        { value: 'call', label: 'Call' },
        { value: 'put', label: 'Put' },
      ],
    },
    { name: 'spot', label: 'Precio spot', kind: 'number', default: 55 },
    { name: 'strike', label: 'Strike', kind: 'number', default: 55 },
    { name: 'volatility', label: 'Volatilidad', kind: 'percent', default: 25 },
    { name: 'rate', label: 'Tasa libre de riesgo', kind: 'percent', default: 7 },
    { name: 'dividend_yield', label: 'Dividendo', kind: 'percent', default: 2 },
    { name: 'maturity_years', label: 'Vencimiento (años)', kind: 'number', default: 1 },
    { name: 'quantity', label: 'Cantidad', kind: 'number', default: 1000 },
  ],
  chart: 'payoff',
};
