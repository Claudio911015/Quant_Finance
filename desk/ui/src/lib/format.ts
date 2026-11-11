// Locale fijo en-US: separador de miles con coma (aprobado en el diseño).
const LOCALE = 'en-US';

/** Un cero negativo (-0, o un -0.001 que redondea a cero) se muestra como cero: nunca "-0.00". */
export function fmtNumber(v: number, decimals: number): string {
  const s = v.toLocaleString(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return /^-0(\.0*)?$/.test(s) ? s.slice(1) : s;
}

export function fmtMoney(v: number, ccy: string): string {
  return `${ccy} ${fmtNumber(v, 2)}`;
}

/** Tasa decimal (0.0725) mostrada en % con 4 decimales. */
export function fmtRate(dec: number): string {
  return `${fmtNumber(dec * 100, 4)} %`;
}

/** Las fechas viajan en ISO (YYYY-MM-DD) y se muestran tal cual. */
export function fmtDate(iso: string): string {
  return iso;
}
