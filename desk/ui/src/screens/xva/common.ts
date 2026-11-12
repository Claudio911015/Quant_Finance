// Utilidades compartidas de la pantalla XVA: unidades de captura, errores y carga de datos.
import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../../api/client';

export const XVA_NOTICE = 'XVA informativo: no entra al PV ni a la contabilidad';
export const COLLATERAL_NOTE =
  'Exposición sin colateral ni margen: la moneda de colateral solo cambia la curva de descuento';

export function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'No se pudo conectar con el backend');
}

/** Decimal de la API (0.006) como texto de un campo en pb ("60"), sin ruido de punto flotante. */
export const toPbText = (dec: number) => String(Number((dec * 1e4).toPrecision(12)));

/** Lo que se teclea en pb viaja como decimal. */
export const fromPb = (pb: number) => Number((pb / 1e4).toPrecision(12));

/** Decimal de la API (0.4) como texto de un campo en % ("40"). */
export const toPercentText = (dec: number) => String(Number((dec * 100).toPrecision(12)));

/** Lo que se teclea en % viaja como decimal. */
export const fromPercent = (pct: number) => Number((pct / 100).toPrecision(12));

/** Número de un campo de texto (acepta comas y espacios); `null` si está vacío o no es finito. */
export function readNumber(raw: string): number | null {
  const cleaned = raw.replace(/[,\s]/g, '');
  if (cleaned === '') return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

export interface Load<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
}

/**
 * Ejecuta `load` al montar y cada vez que cambian `key` o `tick`. Solo la última llamada escribe estado.
 * Con otra `key` (otro snapshot) el dato anterior se descarta; con el mismo `key` (recarga tras guardar)
 * se conserva mientras llega el nuevo.
 */
export function useLoad<T>(load: () => Promise<T>, key: string, tick = 0): Load<T> {
  const [state, setState] = useState<Load<T>>({ data: null, error: null, loading: true });
  const ticket = useRef(0);
  const lastKey = useRef<string | null>(null);
  const loader = useRef(load);
  loader.current = load;

  useEffect(() => {
    const mine = ++ticket.current;
    const same = lastKey.current === key;
    lastKey.current = key;
    setState((s) => ({ data: same ? s.data : null, error: null, loading: true }));
    loader.current().then(
      (data) => {
        if (mine === ticket.current) setState({ data, error: null, loading: false });
      },
      (e) => {
        if (mine === ticket.current) setState({ data: null, error: toApiError(e), loading: false });
      },
    );
    return () => {
      ticket.current++;
    };
  }, [key, tick]);

  return state;
}
