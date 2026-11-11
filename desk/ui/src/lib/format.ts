// Locale fijo en-US: separador de miles con coma (aprobado en el diseño).
const LOCALE = 'en-US';

export function fmtNumber(v: number, decimals: number): string {
  return v.toLocaleString(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
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
