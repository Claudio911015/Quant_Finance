import type { HistorySource, LimitMetric, LimitScope, LimitStatus } from '../../api/riskTypes';

export const RISK_TABS = [
  { id: 'sensibilidades', label: 'Sensibilidades' },
  { id: 'var', label: 'VaR' },
  { id: 'pnl', label: 'P&L explicado' },
  { id: 'limites', label: 'Límites' },
  { id: 'credito', label: 'Crédito' },
  { id: 'escenarios', label: 'Escenarios' },
] as const;

export type RiskTabId = (typeof RISK_TABS)[number]['id'];

export const LIMIT_SCOPE_LABEL: Record<LimitScope, string> = {
  counterparty: 'Contraparte',
  factor: 'Factor',
  portfolio: 'Portafolio',
};

export const LIMIT_METRIC_LABEL: Record<LimitMetric, string> = {
  pv_exposure: 'Exposición (PV positivo neto)',
  dv01: 'DV01 por curva',
  fx_delta: 'Delta USDMXN (MXN por 1 %)',
  var: 'VaR paramétrico 1 día 99 %',
};

export const LIMIT_STATUS_LABEL: Record<LimitStatus, string> = {
  ok: 'En límite',
  alerta: 'Alerta',
  exceso: 'Exceso',
};

export const HISTORY_SOURCE_LABEL: Record<HistorySource, string> = {
  synthetic: 'Sintética',
  observed: 'Observada',
};
