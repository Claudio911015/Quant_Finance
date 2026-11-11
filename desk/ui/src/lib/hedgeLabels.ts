import type { DedesignationCause, HedgeEvent, HedgeStatus, HedgeType, ItemKind, ReleaseCause } from '../api/types';

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
  // Lado del swap en el término crítico "Sentido": paga o cobra la tasa fija.
  payer: 'Paga fija',
  receiver: 'Cobra fija',
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
  reserve_release: 'Liberación de reserva',
};

export const DEDESIGNATION_CAUSE_LABEL: Record<DedesignationCause, string> = {
  instrument_ended: 'El instrumento venció, se vendió o se terminó',
  criteria_not_met: 'La relación deja de cumplir los criterios',
  risk_objective_changed: 'Cambió el objetivo de gestión de riesgo',
};

export const RELEASE_CAUSE_LABEL: Record<ReleaseCause, string> = {
  flow_occurred: 'El flujo cubierto ocurrió',
  flow_no_longer_expected: 'El flujo cubierto ya no se espera',
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

/** Campo del formulario o de las acciones al que se refiere cada clave que el backend cita entre comillas. */
const KEY_LABEL: Record<string, string> = {
  trade_id: 'Operación',
  hedge_type: 'Tipo',
  item_kind: 'Partida',
  index: 'Índice',
  notional: 'Nocional',
  amount_usd: 'Monto USD',
  start_date: 'Inicio',
  maturity_date: 'Vencimiento',
  date: 'Fecha',
  side: 'Lado',
  fraction: 'Fracción',
  hedge_ratio: 'Razón de cobertura',
  reason: 'Motivo',
  snapshot: 'Snapshot',
  cause: 'Causa',
  amount: 'Monto',
  ...DOC_FIELD_LABEL,
};

/** Identificadores que el backend deja sueltos dentro de una frase (tipos, partidas y productos). */
const TOKEN_LABEL: Record<string, string> = {
  cash_flow: 'flujo de efectivo',
  fair_value: 'valor razonable',
  floating_loan: 'crédito a tasa variable',
  fixed_loan: 'crédito a tasa fija',
  forecast_fx: 'flujo pronosticado en USD',
  irs: 'swap de tasas',
  fx_forward: 'forward FX',
};

/**
 * Los mensajes de error del backend citan claves ('fraction') e identificadores (floating_loan, irs)
 * del contrato; aquí se muestran con los nombres que ve el usuario en pantalla.
 */
export function localizeMessage(message: string): string {
  let first = true;
  const withLabels = message.replace(/'([a-z_]+)'/g, (whole, key: string) => {
    const label = KEY_LABEL[key];
    if (label === undefined) return whole;
    const atStart = first;
    first = false;
    return atStart ? label : label.charAt(0).toLowerCase() + label.slice(1);
  });
  return withLabels.replace(/\b[a-z]+(?:_[a-z]+)+\b|\birs\b/g, (token) => TOKEN_LABEL[token] ?? token);
}
