// Rótulos en español de las pantallas de operaciones (corte 5).
import type { ProductId } from '../../api/types';
import type { FlowStatus, ReconStatus } from '../../api/opsTypes';

export const FLOW_STATUS_LABEL: Record<FlowStatus, string> = {
  settled: 'Liquidado',
  confirmed: 'Confirmado',
  projected: 'Proyectado',
};

export const FLOW_KIND_LABEL = {
  coupon: 'Cupón',
  settlement: 'Liquidación',
  transfer: 'Transferencia',
} as const;

export const RECON_STATUS_LABEL: Record<ReconStatus, string> = {
  conciliada: 'Conciliada',
  explicable: 'Explicable',
  revisar: 'Revisar',
};

export const PRODUCT_LABEL: Record<ProductId, string> = {
  irs: 'Swap de tasa',
  fx_forward: 'Forward USD/MXN',
  fx_option: 'Opción USD/MXN',
  cap_floor: 'Cap / floor',
  swaption: 'Swaption',
  bond: 'Bono',
  equity_option: 'Opción de renta variable',
};

/** Productos que exportan a FpML (espejo de `FPML_PRODUCTS` del backend). */
export const FPML_PRODUCTS: ProductId[] = ['irs', 'fx_forward', 'fx_option'];

/** Encabezado del CSV del banco; sirve de `placeholder` del área de pegado. */
export const CSV_TEMPLATE = 'trade_id,bank_pv,currency,bank_ref\n';
