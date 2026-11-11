/**
 * Supuestos contables que la metodología de coberturas declara. Son una sola fuente: la pantalla de
 * Metodología los incorpora a sus filas y el reporte de cada relación los lista tal cual.
 */

export const DECL_RECYCLING =
  'El reciclaje se reconoce cuando liquida el flujo cubierto proxy (el derivado hipotético), con el supuesto de que la partida afecta resultados en esa misma fecha.';

export const DECL_FV_COMPONENT =
  'En valor razonable la partida se mide por su componente de tasa de referencia (un swap a la par a la designación; IFRS 9 6.3.7), no por su cupón contractual, y el ajuste de la partida no se amortiza.';

export const DECL_FV_PRESENTATION =
  'El cupón neto del swap de valor razonable se presenta en la cuenta de cobertura, no en gasto por intereses.';

export const DECL_DEDESIGNATION =
  'Desdesignar exige una causa (IFRS 9 6.5.6): no hay desdesignación voluntaria de una relación que sigue cumpliendo el objetivo de gestión de riesgo.';

export const DECL_OFF_MARKET =
  'Un derivado fuera de mercado al designar trae un valor inicial que ya está en libros y no genera asiento; es fuente de inefectividad.';

export const HEDGE_DECLARATIONS: string[] = [
  DECL_RECYCLING,
  DECL_FV_COMPONENT,
  DECL_FV_PRESENTATION,
  DECL_DEDESIGNATION,
  DECL_OFF_MARKET,
];
