// Rótulos en español de las pantallas de operaciones (corte 5).
import type { ProductId } from '../../api/types';
import type { FlowStatus, ReconStatus } from '../../api/opsTypes';

export const FLOW_STATUS_LABEL: Record<FlowStatus, string> = {
  settled: 'Liquidado',
  confirmed: 'Confirmado',
  projected: 'Proyectado',
};

// Los rótulos de tipo de flujo y de producto son los de la ficha y Pricers: `FLOW_KIND_LABEL` (lib/csaLabels) y
// `productTitle` (pricers/registry); aquí no se repiten.
export { FLOW_KIND_LABEL } from '../../lib/csaLabels';

export const RECON_STATUS_LABEL: Record<ReconStatus, string> = {
  conciliada: 'Conciliada',
  explicable: 'Explicable',
  revisar: 'Revisar',
};

/** Productos que exportan a FpML (espejo de `FPML_PRODUCTS` del backend). */
export const FPML_PRODUCTS: ProductId[] = ['irs', 'fx_forward', 'fx_option'];

/** Productos sin plantilla de confirmación imprimible (espejo del backend: por ahora el cross currency swap). */
export const NO_CONFIRMATION_PRODUCTS: ProductId[] = ['xccy_swap'];

/** Encabezado del CSV del banco; sirve de `placeholder` del área de pegado. */
export const CSV_TEMPLATE = 'trade_id,bank_pv,currency,bank_ref\n';
