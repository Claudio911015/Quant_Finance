import type { CollateralCurrency } from '../api/types';

/** Rótulos de colateral, patas y cross currency swap (corte 3). */

export const COLLATERAL_LABEL: Record<CollateralCurrency, string> = {
  MXN: 'Colateral en MXN',
  USD: 'Colateral en USD',
};

export const LEG_LABEL: Record<'USD' | 'MXN', string> = {
  USD: 'Pata USD (SOFR)',
  MXN: 'Pata MXN (TIIE-F + diferencial)',
};

/** Tipos de flujo nuevos; `TradeScreen` los suma a los que ya rotula. */
export const FLOW_KIND_EXTRA_LABEL: Record<'exchange' | 'redemption', string> = {
  exchange: 'Intercambio de nocional',
  redemption: 'Amortización',
};

export const XCCY_SIDE_LABEL: Record<'pay_usd' | 'pay_mxn', string> = {
  pay_usd: 'Paga USD / recibe MXN',
  pay_mxn: 'Paga MXN / recibe USD',
};

export const EXCHANGE_LABEL: Record<'both' | 'initial' | 'final' | 'none', string> = {
  both: 'Inicial y final',
  initial: 'Solo inicial',
  final: 'Solo final',
  none: 'Sin intercambio',
};

export const CSA_CURVE_NOTE =
  'Curva dependiente: se recalibra con los puntos forward y la base fijos cuando se mueven SOFR, TIIE-F o el spot';

export const NO_CSA_TEXT = 'Sin curva MXN-USD en este snapshot: se descuenta con TIIE-F';
