import type { HedgeEvent, HedgeStatus, HedgeType, ItemKind } from '../api/types';

export const HEDGE_TYPE_LABEL: Record<HedgeType, string> = {
  cash_flow: 'Flujo de efectivo',
  fair_value: 'Valor razonable',
};

export const ITEM_KIND_LABEL: Record<ItemKind, string> = {
  floating_loan: 'Crédito a tasa variable',
  fixed_loan: 'Crédito a tasa fija',
  forecast_fx: 'Flujo pronosticado en USD',
};

export const SIDE_LABEL: Record<string, string> = {
  pays_floating: 'Paga variable',
  receives_floating: 'Cobra variable',
  pays_fixed: 'Paga fija',
  receives_fixed: 'Cobra fija',
  buy_usd: 'Compra de USD',
  sell_usd: 'Venta de USD',
  buy: 'Compra',
  sell: 'Venta',
};

/** Partidas cubiertas admitidas por tipo de cobertura (el backend rechaza el resto con 400). */
export const VALID_ITEM_KINDS: Record<HedgeType, ItemKind[]> = {
  cash_flow: ['floating_loan', 'forecast_fx'],
  fair_value: ['fixed_loan'],
};

export const HEDGE_STATUS_LABEL: Record<HedgeStatus, string> = {
  activa: 'Activa',
  desdesignada: 'Desdesignada',
};

export const HEDGE_EVENT_LABEL: Record<HedgeEvent['type'], string> = {
  designation: 'Designación',
  period_close: 'Cierre de periodo',
  dedesignation: 'Desdesignación',
};

export const TERM_RESULT_LABEL = {
  match: 'Coincide',
  mismatch: 'No coincide',
} as const;

export const DOC_FIELD_LABEL = {
  risk_management_objective: 'Objetivo de gestión de riesgo',
  hedged_risk: 'Riesgo cubierto',
  effectiveness_method: 'Método de efectividad',
  ineffectiveness_sources: 'Fuentes de inefectividad',
} as const;

export const DEFAULT_EFFECTIVENESS_METHOD =
  'Coincidencia de términos críticos y análisis de escenarios con derivado hipotético';
