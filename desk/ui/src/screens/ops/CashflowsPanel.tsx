import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { cashflowsCsvUrl, confirmSettlement, getCashflows } from '../../api/opsClient';
import type { CashflowRow, CashflowsQuery, CashflowsResponse, OpsCurrency } from '../../api/opsTypes';
import { fmtDate, fmtMoney, fmtNumber, parseNumber } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import { productTitle } from '../pricers/registry';
import { FLOW_KIND_LABEL, FLOW_STATUS_LABEL } from './opsLabels';
import './CashflowsPanel.css';

/** Días hacia atrás desde el `as_of` con que abre el filtro "Desde": se ven los liquidados recientes y los proyectados. */
const DEFAULT_LOOKBACK_DAYS = 90;
// Un aviso de fijaciones faltantes puede nombrar cientos de días: se muestran los primeros y se cuenta el resto.
const MAX_WARNING_DATES = 5;

type CurrencyFilter = '' | OpsCurrency;

/** `YYYY-MM-DD` menos `days` días naturales (aritmética en UTC: sin saltos de horario de verano). */
function shiftDate(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

function isOpsCurrency(c: string): c is OpsCurrency {
  return c === 'MXN' || c === 'USD';
}

/** Solo un flujo ya liquidado y todavía sin confirmar, de cupón o de liquidación, admite confirmación. */
function canConfirm(row: CashflowRow): boolean {
  return (
    row.status === 'settled' && (row.kind === 'coupon' || row.kind === 'settlement') && isOpsCurrency(row.currency)
  );
}

/** Un flujo se identifica por operación y fecha: el backend admite una sola confirmación por par. */
function flowKey(row: CashflowRow): string {
  return `${row.trade_id}|${row.date}`;
}

/** Monto con cifras tabulares; el negativo se marca y nunca sale "-0.00". */
function Amount({ value }: { value: number | null }) {
  if (value == null) return <>—</>;
  return <span className={value < 0 ? 'ops-cash__neg' : undefined}>{fmtNumber(value, 2)}</span>;
}

interface ConfirmFormProps {
  row: CashflowRow;
  snapshotId: string;
  onDone(): void;
  onCancel(): void;
}

/** Formulario en línea para confirmar el monto que el banco liquidó realmente; moneda fija la del flujo. */
function ConfirmForm({ row, snapshotId, onDone, onCancel }: ConfirmFormProps) {
  // Sin separador de miles: es un valor para editar, no para leer (y fmtNumber evita "-0.00").
  const [value, setValue] = useState(fmtNumber(row.amount, 2).replace(/,/g, ''));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = `ops-cash-amount-${row.trade_id}-${row.date}`;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const amount = parseNumber(value);
    if (amount === null) {
      setError('El monto debe ser un número.');
      return;
    }
    if (!isOpsCurrency(row.currency)) return;
    setBusy(true);
    setError(null);
    try {
      await confirmSettlement(row.trade_id, {
        date: row.date,
        amount,
        currency: row.currency,
        snapshot: snapshotId,
      });
      onDone();
    } catch (err) {
      setError(describe(err));
      setBusy(false);
    }
  };

  return (
    <form
      className="ops-cash__form"
      onSubmit={submit}
      aria-label={`Confirmar liquidación de la operación ${row.trade_id} del ${fmtDate(row.date)}`}
    >
      <label htmlFor={id}>Monto liquidado por el banco</label>
      <input
        id={id}
        className="ops-cash__input num"
        inputMode="decimal"
        value={value}
        aria-invalid={error ? true : undefined}
        onChange={(e) => setValue(e.target.value)}
      />
      <span className="ops-cash__ccy" title="Moneda del flujo">
        {row.currency}
      </span>
      <button type="submit" className="ops-cash__btn" disabled={busy}>
        Confirmar
      </button>
      <button type="button" className="ops-cash__btn" onClick={onCancel} disabled={busy}>
        Cancelar
      </button>
      {error && (
        <p className="ops-cash__form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

const COLUMNS = [
  'Fecha',
  'Operación',
  'Contraparte',
  'Producto',
  'Tipo',
  'Estado',
  'Moneda',
  'Monto',
  'Monto MXN',
  'Confirmado',
  'Diferencia',
];

export function CashflowsPanel() {
  const { snapshotId, snapshot } = useSnapshot();
  // `snapshot` se anula al cambiar de snapshot: hasta que coincida con el activo no hay `as_of` fiable.
  const asOf = snapshot && snapshot.id === snapshotId ? snapshot.as_of : null;
  // `undefined` = el valor por omisión (as_of − 90 días); '' = sin límite, elegido por el usuario.
  const [fromInput, setFromInput] = useState<string | undefined>(undefined);
  const [to, setTo] = useState('');
  const [counterparty, setCounterparty] = useState('');
  const [currency, setCurrency] = useState<CurrencyFilter>('');
  const [data, setData] = useState<CashflowsResponse | null>(null);
  const [counterparties, setCounterparties] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  // Cada carga toma un número; solo la última escribe estado (una respuesta lenta de una
  // consulta anterior no debe pisar la de los filtros elegidos después).
  const latest = useRef(0);

  const from = fromInput ?? (asOf ? shiftDate(asOf, DEFAULT_LOOKBACK_DAYS) : '');
  const ready = asOf !== null;

  const query = useCallback((): CashflowsQuery => {
    const q: CashflowsQuery = { snapshot: snapshotId };
    if (from) q.from = from;
    if (to) q.to = to;
    if (counterparty) q.counterparty = counterparty;
    if (currency) q.currency = currency;
    return q;
  }, [snapshotId, from, to, counterparty, currency]);

  const load = useCallback(async () => {
    if (!ready) return;
    const ticket = ++latest.current;
    const q = query();
    setLoading(true);
    try {
      const res = await getCashflows(q);
      if (ticket !== latest.current) return;
      setData(res);
      setError(null);
      setOpen(null);
      // Las contrapartes salen de una consulta sin filtro de contraparte; con una elegida se conserva la lista.
      if (!q.counterparty) {
        setCounterparties(Array.from(new Set(res.rows.map((r) => r.counterparty))).sort());
      }
    } catch (e) {
      if (ticket !== latest.current) return;
      setData(null);
      setError(describe(e));
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  }, [ready, query]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!ready) {
    return <p className="ops-cash__meta">Cargando snapshot…</p>;
  }

  // La contraparte elegida siempre figura en la lista, aunque la última consulta ya no la traiga.
  const options = counterparty && !counterparties.includes(counterparty) ? [...counterparties, counterparty] : counterparties;
  const rows = data?.rows ?? [];

  return (
    <div className="ops-cash">
      <div className="ops-cash__filters">
        <div className="ops-cash__field">
          <label htmlFor="ops-cash-from">Desde</label>
          <input
            id="ops-cash-from"
            type="date"
            className="ops-cash__input"
            value={from}
            onChange={(e) => setFromInput(e.target.value)}
          />
        </div>
        <div className="ops-cash__field">
          <label htmlFor="ops-cash-to">Hasta</label>
          <input
            id="ops-cash-to"
            type="date"
            className="ops-cash__input"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <div className="ops-cash__field">
          <label htmlFor="ops-cash-cp">Contraparte</label>
          <select
            id="ops-cash-cp"
            className="ops-cash__input"
            value={counterparty}
            onChange={(e) => setCounterparty(e.target.value)}
          >
            <option value="">Todas</option>
            {options.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="ops-cash__field">
          <label htmlFor="ops-cash-ccy">Moneda</label>
          <select
            id="ops-cash-ccy"
            className="ops-cash__input"
            value={currency}
            onChange={(e) => setCurrency(e.target.value as CurrencyFilter)}
          >
            <option value="">Todas</option>
            <option value="MXN">MXN</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <a className="ops-cash__btn ops-cash__export" href={cashflowsCsvUrl(query())} download>
          Exportar CSV
        </a>
      </div>

      {data && (
        <p className="ops-cash__meta">
          Snapshot {data.snapshot} · al {fmtDate(data.as_of)} · {rows.length} {rows.length === 1 ? 'flujo' : 'flujos'}
          {loading && ' · actualizando…'}
        </p>
      )}
      {!data && loading && <p className="ops-cash__meta">Cargando flujos…</p>}
      {error && (
        <p className="ops-cash__banner" role="alert">
          {error}
        </p>
      )}

      {data && data.errors.length > 0 && (
        <ul className="ops-cash__notes" aria-label="Operaciones sin flujos">
          {data.errors.map((e) => (
            <li key={e.trade_id} className="ops-cash__note">
              Operación {e.trade_id}: {e.message}
            </li>
          ))}
        </ul>
      )}
      {data && data.warnings.length > 0 && (
        <ul className="ops-cash__notes" aria-label="Avisos">
          {data.warnings.map((w, i) => (
            <li key={`${w.code}-${i}`} className="ops-cash__note">
              {w.message}
              {w.dates.length > 0 && (
                <span className="ops-cash__dim" title={w.dates.map(fmtDate).join(', ')}>
                  {' '}
                  ({w.dates.slice(0, MAX_WARNING_DATES).map(fmtDate).join(', ')}
                  {w.dates.length > MAX_WARNING_DATES && ` … y ${w.dates.length - MAX_WARNING_DATES} más`})
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {data && (
        <div className="ops-cash__scroll">
          <table className="ops-cash__table" aria-label="Flujos">
            <thead>
              <tr>
                {COLUMNS.map((c, i) => (
                  <th key={c} className={i >= 7 ? 'num' : undefined}>
                    {c}
                  </th>
                ))}
                <th>
                  <span className="ops-cash__sr">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length + 1} className="ops-cash__empty">
                    Sin flujos con esos filtros.
                  </td>
                </tr>
              )}
              {rows.map((r, i) => {
                const key = flowKey(r);
                const formOpen = open === key && canConfirm(r);
                return [
                  <tr key={`${key}|${r.kind}|${i}`} className={`ops-cash__row ops-cash__row--${r.status}`}>
                    <td className="num">{fmtDate(r.date)}</td>
                    <td>
                      <Link to={`/portafolio/${r.trade_id}`}>#{r.trade_id}</Link>
                    </td>
                    <td>{r.counterparty}</td>
                    <td>{productTitle(r.product)}</td>
                    <td>{FLOW_KIND_LABEL[r.kind] ?? r.kind}</td>
                    <td>{FLOW_STATUS_LABEL[r.status] ?? r.status}</td>
                    <td>{r.currency}</td>
                    <td className="num">
                      <Amount value={r.amount} />
                    </td>
                    <td className="num">
                      <Amount value={r.amount_mxn} />
                    </td>
                    <td className="num">
                      <Amount value={r.confirmed_amount} />
                    </td>
                    <td className="num">
                      <Amount value={r.difference} />
                    </td>
                    <td>
                      {canConfirm(r) && (
                        <button
                          type="button"
                          className="ops-cash__btn"
                          aria-expanded={formOpen}
                          onClick={() => setOpen(formOpen ? null : key)}
                        >
                          Confirmar liquidación
                        </button>
                      )}
                    </td>
                  </tr>,
                  formOpen && (
                    <tr key={`${key}|form`} className="ops-cash__form-row">
                      <td colSpan={COLUMNS.length + 1}>
                        <div className="ops-cash__form-wrap">
                          <ConfirmForm
                            row={r}
                            snapshotId={snapshotId}
                            onCancel={() => setOpen(null)}
                            onDone={() => {
                              setOpen(null);
                              void load();
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ),
                ];
              })}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <section className="ops-cash__totals" aria-label="Totales">
          <div className="ops-cash__total-main">
            <span className="ops-cash__dim">Total (MXN)</span>
            <strong className={`num${data.totals.amount_mxn < 0 ? ' ops-cash__neg' : ''}`}>
              {fmtMoney(data.totals.amount_mxn, 'MXN')}
            </strong>
          </div>
          <table className="ops-cash__table ops-cash__table--small" aria-label="Totales por moneda">
            <thead>
              <tr>
                <th>Moneda</th>
                <th className="num">Monto</th>
                <th className="num">Monto MXN</th>
                <th className="num">Flujos</th>
              </tr>
            </thead>
            <tbody>
              {data.totals.by_currency.map((t) => (
                <tr key={t.currency}>
                  <td>{t.currency}</td>
                  <td className="num">
                    <Amount value={t.amount} />
                  </td>
                  <td className="num">
                    <Amount value={t.amount_mxn} />
                  </td>
                  <td className="num">{t.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <table className="ops-cash__table ops-cash__table--small" aria-label="Totales por contraparte">
            <thead>
              <tr>
                <th>Contraparte</th>
                <th className="num">Monto MXN</th>
                <th className="num">Flujos</th>
              </tr>
            </thead>
            <tbody>
              {data.totals.by_counterparty.map((t) => (
                <tr key={t.counterparty}>
                  <td>{t.counterparty}</td>
                  <td className="num">
                    <Amount value={t.amount_mxn} />
                  </td>
                  <td className="num">{t.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
