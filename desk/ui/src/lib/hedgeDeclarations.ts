/**
 * Supuestos contables que la metodología de coberturas declara. Son una sola fuente: la pantalla de
 * Metodología los incorpora a sus filas y el reporte de cada relación los lista tal cual.
 */

export const DECL_RECYCLING =
  'El reciclaje se reconoce cuando liquida el flujo cubierto proxy (el derivado hipotético), con el supuesto de que la partida afecta resultados en esa misma fecha.';

export const DECL_FV_COMPONENT =
  'En valor razonable la partida se mide por su componente de tasa de referencia (un swap a la par a la designación; IFRS 9 6.3.7), no por su cupón contractual, y el ajuste de la partida no se amortiza.';

export const DECL_FV_ACCRUAL =
  'En valor razonable el ajuste de la partida es el cambio del valor del swap hipotético a la par, que incluye el devengo del cupón en curso: no es un valor limpio, así que entre fechas de cupón incorpora el diferencial devengado y lo revierte al pagarse.';

export const DECL_FV_PRESENTATION =
  'El cupón neto del swap de valor razonable se presenta en la cuenta de cobertura, no en gasto por intereses.';

export const DECL_DEDESIGNATION =
  'Desdesignar exige una causa (IFRS 9 6.5.6): no hay desdesignación voluntaria de una relación que sigue cumpliendo el objetivo de gestión de riesgo.';

export const DECL_DESIGNATION_DATE =
  'El sistema controla el orden cronológico entre las relaciones de una misma operación, pero no puede comprobar que la documentación existiera en la fecha de designación (IFRS 9 6.4.1(b)): una cobertura se puede documentar con un snapshot pasado. El alta avisa si se documenta más de un día después y el reporte muestra ambas fechas.';

export const DECL_OFF_MARKET =
  'Un derivado fuera de mercado al designar trae un valor inicial que ya está en libros y no genera asiento; es fuente de inefectividad.';

export const DECL_HEDGE_RATIO =
  'La medición compara la fracción designada del instrumento completo contra la partida completa, sin escalar ninguno por la razón de cobertura: la razón capturada (unidades de instrumento por unidad de partida) es informativa, solo entra a la comparación de nocional de los términos críticos y, si difiere de la que implican los nocionales en más de 1 %, el alta avisa. Una razón distinta de la de los nocionales no cambia la inefectividad.';

export const HEDGE_DECLARATIONS: string[] = [
  DECL_RECYCLING,
  DECL_FV_COMPONENT,
  DECL_FV_ACCRUAL,
  DECL_FV_PRESENTATION,
  DECL_DEDESIGNATION,
  DECL_DESIGNATION_DATE,
  DECL_OFF_MARKET,
  DECL_HEDGE_RATIO,
];
