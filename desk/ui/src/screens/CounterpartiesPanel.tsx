import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, listCounterparties, setCollateral } from '../api/client';
import type { CollateralCurrency, Counterparty } from '../api/types';
import { fmtDate, fmtDateTime } from '../lib/format';
import { COLLATERAL_LABEL } from '../lib/csaLabels';
import './CounterpartiesPanel.css';

const CURRENCIES: CollateralCurrency[] = ['MXN', 'USD'];

type FieldName = 'collateral_currency' | 'effective_date';

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

interface FormProps {
  counterparty: Counterparty;
  /** Fecha efectiva propuesta: el `as_of` del snapshot activo. */
  defaultDate: string;
  onDone(): Promise<void>;
  onCancel(): void;
}

/** Cambio de colateral de una contraparte; los errores 400/409 del backend van bajo su campo. */
function CollateralForm({ counterparty, defaultDate, onDone, onCancel }: FormProps) {
  // Se propone la otra moneda: el backend rechaza (409) repetir la vigente.
  const [currency, setCurrency] = useState<CollateralCurrency>(
    counterparty.collateral_currency === 'USD' ? 'MXN' : 'USD',
  );
  const [date, setDate] = useState(defaultDate);
  const [errors, setErrors] = useState<Partial<Record<FieldName | 'general', string>>>({});
  const [busy, setBusy] = useState(false);
  const currencyId = `cp-${counterparty.id}-currency`;
  const dateId = `cp-${counterparty.id}-date`;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!date) {
      setErrors({ effective_date: 'Indica la fecha efectiva' });
      return;
    }
    setErrors({});
    setBusy(true);
    try {
      await setCollateral(counterparty.id, { collateral_currency: currency, effective_date: date });
    } catch (err) {
      if (
        err instanceof ApiError &&
        (err.status === 400 || err.status === 409) &&
        (err.field === 'collateral_currency' || err.field === 'effective_date')
      ) {
        setErrors({ [err.field]: err.message });
      } else {
        setErrors({ general: describe(err) });
      }
      setBusy(false);
      return;
    }
    // El cambio ya está guardado: aunque la recarga falle, el formulario se cierra.
    setBusy(false);
    await onDone();
  };

  return (
    <form
      className="counterparties__form"
      onSubmit={submit}
      noValidate
      aria-label={`Cambiar colateral de ${counterparty.name}`}
    >
      <div className="counterparties__field">
        <label htmlFor={currencyId}>Moneda del colateral</label>
        <select
          id={currencyId}
          className="counterparties__input"
          value={currency}
          aria-invalid={errors.collateral_currency ? true : undefined}
          onChange={(e) => setCurrency(e.target.value as CollateralCurrency)}
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        {errors.collateral_currency && (
          <div className="counterparties__error" role="alert">
            {errors.collateral_currency}
          </div>
        )}
      </div>
      <div className="counterparties__field">
        <label htmlFor={dateId}>Fecha efectiva</label>
        <input
          id={dateId}
          type="date"
          className="counterparties__input"
          value={date}
          aria-invalid={errors.effective_date ? true : undefined}
          onChange={(e) => setDate(e.target.value)}
        />
        {errors.effective_date && (
          <div className="counterparties__error" role="alert">
            {errors.effective_date}
          </div>
        )}
      </div>
      <div className="counterparties__actions">
        <button type="submit" className="counterparties__btn counterparties__btn--primary" disabled={busy}>
          Aplicar
        </button>
        <button type="button" className="counterparties__btn" onClick={onCancel} disabled={busy}>
          Cancelar
        </button>
      </div>
      {errors.general && (
        <div className="counterparties__error counterparties__error--wide" role="alert">
          {errors.general}
        </div>
      )}
    </form>
  );
}

/**
 * Contrapartes con la moneda de colateral vigente y su historial.
 * `asOf` es la fecha efectiva propuesta (el `as_of` del snapshot activo); `onChanged` avisa al
 * llamador de que un cambio de colateral movió valuaciones (el blotter se recarga).
 */
export default function CounterpartiesPanel({
  asOf,
  onChanged,
}: {
  asOf: string | null;
  onChanged?: () => void;
}) {
  const [rows, setRows] = useState<Counterparty[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());
  // Solo la última carga escribe estado.
  const latest = useRef(0);

  const load = useCallback(async () => {
    const ticket = ++latest.current;
    setLoading(true);
    try {
      const list = await listCounterparties();
      if (ticket !== latest.current) return;
      setRows(list);
      setError(null);
    } catch (e) {
      if (ticket !== latest.current) return;
      setError(describe(e));
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleHistory = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const done = async () => {
    setEditing(null);
    await load();
    onChanged?.();
  };

  return (
    <div className="counterparties">
      <header className="counterparties__head">
        <h2>Contrapartes</h2>
        <span className="counterparties__meta">
          {loading ? 'Cargando…' : rows ? `${rows.length} contrapartes` : ''}
        </span>
      </header>
      <p className="counterparties__note">
        El colateral de cada contraparte decide con qué curva se descuentan sus flujos en MXN a partir de
        la fecha efectiva.
      </p>
      {error && (
        <div className="counterparties__banner" role="alert">
          {error}
        </div>
      )}
      {rows && rows.length === 0 && !error && (
        <p className="counterparties__empty">Sin contrapartes. Aparecen al agregar una operación.</p>
      )}
      {rows && rows.length > 0 && (
        <div className="counterparties__scroll">
          <table className="counterparties__table">
            <thead>
              <tr>
                <th>Contraparte</th>
                <th className="num">Operaciones</th>
                <th>Colateral vigente</th>
                <th>Desde</th>
                <th>
                  <span className="counterparties__sr">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((cp) => {
                const open = expanded.has(cp.id);
                return (
                  <Fragment key={cp.id}>
                    <tr>
                      <td>{cp.name}</td>
                      <td className="num">{cp.trades}</td>
                      <td>{COLLATERAL_LABEL[cp.collateral_currency]}</td>
                      <td className="counterparties__date">{cp.effective_date ? fmtDate(cp.effective_date) : '—'}</td>
                      <td>
                        <div className="counterparties__row-actions">
                          <button
                            type="button"
                            className="counterparties__btn"
                            aria-label={`Cambiar colateral de ${cp.name}`}
                            aria-expanded={editing === cp.id}
                            onClick={() => setEditing(editing === cp.id ? null : cp.id)}
                          >
                            Cambiar colateral
                          </button>
                          <button
                            type="button"
                            className="counterparties__btn"
                            aria-label={`Historial de ${cp.name}`}
                            aria-expanded={open}
                            onClick={() => toggleHistory(cp.id)}
                          >
                            Historial
                          </button>
                        </div>
                      </td>
                    </tr>
                    {editing === cp.id && (
                      <tr className="counterparties__detail">
                        <td colSpan={5}>
                          <CollateralForm
                            counterparty={cp}
                            defaultDate={asOf ?? ''}
                            onDone={done}
                            onCancel={() => setEditing(null)}
                          />
                        </td>
                      </tr>
                    )}
                    {open && (
                      <tr className="counterparties__detail">
                        <td colSpan={5}>
                          {cp.history.length === 0 ? (
                            <p className="counterparties__empty">
                              Sin cambios registrados: {cp.name} tiene colateral en MXN desde el inicio.
                            </p>
                          ) : (
                            <table
                              className="counterparties__table counterparties__history"
                              aria-label={`Historial de colateral de ${cp.name}`}
                            >
                              <thead>
                                <tr>
                                  <th>Fecha efectiva</th>
                                  <th>Moneda</th>
                                  <th>Registrado</th>
                                </tr>
                              </thead>
                              <tbody>
                                {cp.history.map((h) => (
                                  <tr key={h.id}>
                                    <td className="counterparties__date">{fmtDate(h.effective_date)}</td>
                                    <td>{COLLATERAL_LABEL[h.collateral_currency]}</td>
                                    <td className="counterparties__date">{fmtDateTime(h.created_at)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
