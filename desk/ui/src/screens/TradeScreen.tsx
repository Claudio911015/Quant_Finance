import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, getTrade, listHedges, postEvent, tradeFlows, tradeState } from '../api/client';
import type {
  EventType,
  FlowKind,
  FlowsResponse,
  HedgeSummary,
  TradeDetail,
  TradeEvent,
  TradeState,
  TradeStatus,
  Warning,
} from '../api/types';
import { HEDGE_STATUS_LABEL, HEDGE_TYPE_LABEL } from '../lib/hedgeLabels';
import { fmtDate, fmtMoney, fmtNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import { PRODUCT_SPECS } from './pricers/registry';
import './TradeScreen.css';

const STATUS_LABEL: Record<TradeStatus, string> = {
  no_pactada: 'No pactada',
  viva: 'Viva',
  vencida: 'Vencida',
  terminada: 'Terminada',
  ejercida: 'Ejercida',
};

const EVENT_LABEL: Record<EventType, string> = {
  execution: 'Pactada',
  reset: 'Fijación',
  transfer: 'Transferencia',
  quantity_change: 'Cambio de nocional',
  terms_change: 'Cambio de términos',
  exercise: 'Ejercicio',
  termination: 'Terminación anticipada',
};

const FLOW_KIND_LABEL: Record<FlowKind, string> = {
  coupon: 'Cupón',
  settlement: 'Liquidación',
  transfer: 'Transferencia',
};

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

function dash(v: number | null, decimals: number): string {
  return v == null ? '—' : fmtNumber(v, decimals);
}

/** Datos clave de un evento, en una línea. */
function eventSummary(ev: TradeEvent): string {
  const d = ev.data;
  if (ev.type === 'execution') return '';
  if (ev.type === 'quantity_change' && typeof d.notional === 'number') {
    return `Nuevo nocional ${fmtNumber(d.notional, 2)}`;
  }
  if (typeof d.amount === 'number') {
    const ccy = typeof d.currency === 'string' ? d.currency : 'MXN';
    return `Importe ${fmtMoney(d.amount, ccy)}`;
  }
  const terms = d.terms;
  const pairs =
    ev.type === 'terms_change' && terms && typeof terms === 'object'
      ? Object.entries(terms as Record<string, unknown>)
      : Object.entries(d);
  return pairs.map(([k, v]) => `${k}: ${String(v)}`).join(' · ');
}

function Warnings({ warnings }: { warnings: Warning[] }) {
  if (warnings.length === 0) return null;
  return (
    <ul className="trade__warnings" aria-label="Avisos">
      {warnings.map((w, i) => (
        <li key={`${w.code}-${i}`} className="trade__warning">
          {w.message}
          {w.dates.length > 0 && <span className="trade__warning-dates"> ({w.dates.map(fmtDate).join(', ')})</span>}
        </li>
      ))}
    </ul>
  );
}

interface EventFormProps {
  tradeId: number;
  type: 'termination' | 'quantity_change';
  /** Clave del importe en `data` del evento y del campo en los errores del backend. */
  field: 'amount' | 'notional';
  title: string;
  valueLabel: string;
  submitLabel: string;
  defaultDate: string;
  onPosted(): Promise<void>;
  onBanner(message: string | null): void;
}

/** Formulario de un evento con fecha e importe; los errores del backend van bajo su campo. */
function EventForm(p: EventFormProps) {
  const [date, setDate] = useState(p.defaultDate);
  const [value, setValue] = useState('');
  const [errors, setErrors] = useState<Partial<Record<'event_date' | 'amount' | 'notional', string>>>({});
  const [busy, setBusy] = useState(false);
  const dateId = `trade-${p.type}-date`;
  const valueId = `trade-${p.type}-value`;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const raw = value.replace(/[,\s]/g, '');
    const n = Number(raw);
    const local: typeof errors = {};
    if (!date) local.event_date = 'Indica la fecha';
    if (raw === '' || !Number.isFinite(n)) local[p.field] = 'Indica un número';
    if (Object.keys(local).length > 0) {
      setErrors(local);
      return;
    }
    setErrors({});
    p.onBanner(null);
    setBusy(true);
    try {
      await postEvent(p.tradeId, { type: p.type, event_date: date, data: { [p.field]: n } });
      setValue('');
      await p.onPosted();
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && (err.field === 'event_date' || err.field === p.field)) {
        setErrors({ [err.field]: err.message });
      } else {
        p.onBanner(describe(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="trade__form" onSubmit={submit} noValidate aria-label={p.title}>
      <h3>{p.title}</h3>
      <div className="trade__field">
        <label htmlFor={dateId}>Fecha</label>
        <input
          id={dateId}
          type="date"
          className="trade__input"
          value={date}
          aria-invalid={errors.event_date ? true : undefined}
          onChange={(e) => setDate(e.target.value)}
        />
        {errors.event_date && (
          <div className="trade__error" role="alert">
            {errors.event_date}
          </div>
        )}
      </div>
      <div className="trade__field">
        <label htmlFor={valueId}>{p.valueLabel}</label>
        <input
          id={valueId}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          className="trade__input num"
          value={value}
          aria-invalid={errors[p.field] ? true : undefined}
          onChange={(e) => setValue(e.target.value)}
        />
        {errors[p.field] && (
          <div className="trade__error" role="alert">
            {errors[p.field]}
          </div>
        )}
      </div>
      <button type="submit" className="trade__btn" disabled={busy}>
        {p.submitLabel}
      </button>
    </form>
  );
}

export default function TradeScreen() {
  const { id: idParam } = useParams();
  const id = idParam != null && /^\d+$/.test(idParam) ? Number(idParam) : null;
  const { snapshotId, snapshot, error: snapshotError } = useSnapshot();
  // El snapshot completo llega después de elegir el id: sin él no hay fecha de valuación.
  const asOf = snapshot && snapshot.id === snapshotId ? snapshot.as_of : null;

  const [trade, setTrade] = useState<TradeDetail | null>(null);
  const [state, setState] = useState<TradeState | null>(null);
  const [flows, setFlows] = useState<FlowsResponse | null>(null);
  const [flowsError, setFlowsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [hedges, setHedges] = useState<HedgeSummary[]>([]);
  // Cada carga toma un número; solo la última escribe estado (una respuesta lenta de un
  // snapshot anterior no debe pisar la del que el usuario eligió después).
  const latest = useRef(0);

  const load = useCallback(async () => {
    if (id == null || asOf == null) return;
    const ticket = ++latest.current;
    setLoading(true);
    const [head, fl] = await Promise.allSettled([
      Promise.all([getTrade(id), tradeState(id, asOf)]),
      tradeFlows(id, snapshotId),
    ]);
    if (ticket !== latest.current) return;
    if (head.status === 'fulfilled') {
      setTrade(head.value[0]);
      setState(head.value[1]);
      setError(null);
    } else {
      setTrade(null);
      setState(null);
      setError(describe(head.reason));
    }
    if (fl.status === 'fulfilled') {
      setFlows(fl.value);
      setFlowsError(null);
    } else {
      setFlows(null);
      setFlowsError(describe(fl.reason));
    }
    setActionError(null);
    setLoading(false);
  }, [id, asOf, snapshotId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Las relaciones de cobertura solo informan la ficha: si fallan, la ficha sigue sin la línea.
  useEffect(() => {
    if (id == null) return;
    let cancelled = false;
    listHedges({ trade_id: id }).then(
      (list) => {
        if (!cancelled) setHedges(list);
      },
      () => {
        if (!cancelled) setHedges([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (id == null) {
    return (
      <section className="trade">
        <Link to="/portafolio" className="trade__back">
          Volver al portafolio
        </Link>
        <div className="trade__banner" role="alert">
          Operación inválida
        </div>
      </section>
    );
  }

  const events = trade
    ? [...trade.events].sort((a, b) => a.event_date.localeCompare(b.event_date) || a.id - b.id)
    : [];
  const status = state?.status;
  const spec = trade ? PRODUCT_SPECS[trade.product] : null;
  // Una terminación o un ejercicio, en cualquier fecha, cierra la operación: ya no admite acciones.
  const closing = events.find((ev) => ev.type === 'termination' || ev.type === 'exercise');
  const showActions = closing != null || status === 'no_pactada' || (status === 'viva' && asOf != null);
  const rows = [...(flows?.flows ?? [])].sort((a, b) => a.date.localeCompare(b.date));

  return (
    <section className="trade">
      <Link to="/portafolio" className="trade__back">
        Volver al portafolio
      </Link>

      {(error ?? (asOf == null ? snapshotError : null)) && (
        <div className="trade__banner" role="alert">
          {error ?? snapshotError}
        </div>
      )}
      {!trade && !error && <div className="trade__meta">{loading || asOf == null ? 'Cargando…' : ''}</div>}

      {trade && state && (
        <>
          <header className="trade__head">
            <h1>Operación {trade.id}</h1>
            <span className={`trade__status trade__status--${state.status}`}>
              {STATUS_LABEL[state.status]}
            </span>
            <span className="trade__meta">al {fmtDate(state.date)}</span>
          </header>
          {hedges.map((h) => (
            <Link key={h.id} to={`/coberturas/${h.id}`} className="trade__meta">
              Designada como cobertura #{h.id} · {HEDGE_TYPE_LABEL[h.hedge_type]} · {fmtNumber(h.fraction * 100, 0)}% ·{' '}
              {HEDGE_STATUS_LABEL[h.status]}
            </Link>
          ))}
          <dl className="trade__facts">
            <div>
              <dt>Producto</dt>
              <dd>{spec?.title ?? trade.product}</dd>
            </div>
            <div>
              <dt>Contraparte</dt>
              <dd>{trade.counterparty}</dd>
            </div>
            <div>
              <dt>Pactada</dt>
              <dd className="num">{fmtDate(trade.trade_date)}</dd>
            </div>
            <div>
              <dt>Inicio</dt>
              <dd className="num">{fmtDate(trade.start_date)}</dd>
            </div>
            <div>
              <dt>Vencimiento</dt>
              <dd className="num">{fmtDate(trade.maturity_date)}</dd>
            </div>
            <div>
              <dt>Nocional vigente</dt>
              <dd className="num">{fmtMoney(state.notional, trade.currency)}</dd>
            </div>
          </dl>

          <div className="trade__cols">
            <section className="trade__block" aria-label="Línea de tiempo">
              <h2>Línea de tiempo</h2>
              <ol className="trade__timeline">
                {events.map((ev) => {
                  const summary = eventSummary(ev);
                  return (
                    <li key={ev.id} className="trade__event">
                      <span className="trade__event-date num">{fmtDate(ev.event_date)}</span>
                      <span className="trade__event-type">{EVENT_LABEL[ev.type]}</span>
                      {summary && <span className="trade__event-data num">{summary}</span>}
                    </li>
                  );
                })}
              </ol>
            </section>

            {showActions && (
              <section className="trade__block" aria-label="Acciones">
                <h2>Acciones</h2>
                {actionError && (
                  <div className="trade__banner" role="alert">
                    {actionError}
                  </div>
                )}
                {closing != null ? (
                  <p className="trade__meta">
                    {closing.type === 'termination' ? 'Terminada' : 'Ejercida'} el {fmtDate(closing.event_date)}
                  </p>
                ) : status === 'no_pactada' ? (
                  <p className="trade__meta">No pactada a esta fecha</p>
                ) : (
                  <>
                    <EventForm
                      key={`termination-${asOf}`}
                      tradeId={trade.id}
                      type="termination"
                      field="amount"
                      title="Terminar anticipadamente"
                      valueLabel="Importe (MXN)"
                      submitLabel="Terminar anticipadamente"
                      defaultDate={asOf!}
                      onPosted={load}
                      onBanner={setActionError}
                    />
                    <EventForm
                      key={`quantity_change-${asOf}`}
                      tradeId={trade.id}
                      type="quantity_change"
                      field="notional"
                      title="Cambiar nocional"
                      valueLabel="Nuevo nocional"
                      submitLabel="Cambiar nocional"
                      defaultDate={asOf!}
                      onPosted={load}
                      onBanner={setActionError}
                    />
                  </>
                )}
              </section>
            )}
          </div>
        </>
      )}

      {trade && (
        <section className="trade__block" aria-label="Calendario de flujos">
          <h2>Calendario de flujos</h2>
          {flowsError && (
            <div className="trade__banner" role="alert">
              {flowsError}
            </div>
          )}
          {flows && <Warnings warnings={flows.warnings} />}
          {flows && rows.length === 0 && <p className="trade__meta">Sin flujos a esta fecha</p>}
          {rows.length > 0 && (
            <table className="trade__flows">
              <thead>
                <tr>
                  <th className="num">Fecha</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th className="num">Monto</th>
                  <th>Moneda</th>
                  <th className="num">DF</th>
                  <th className="num">PV</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((f, i) => (
                  <tr key={`${f.date}-${f.kind}-${i}`} className={`trade__flow trade__flow--${f.status}`}>
                    <td className="num">{fmtDate(f.date)}</td>
                    <td>{FLOW_KIND_LABEL[f.kind]}</td>
                    <td>{f.status === 'settled' ? 'Liquidado' : 'Proyectado'}</td>
                    <td className="num">{fmtNumber(f.amount, 2)}</td>
                    <td>{f.currency}</td>
                    <td className="num">{dash(f.df, 6)}</td>
                    <td className="num">{dash(f.pv, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </section>
  );
}
