import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type ReactNode } from 'react';
import { ApiError, listTrades } from '../../api/client';
import { addLimitEvent, checkLimits, createLimit, limitUsage, listBreaches } from '../../api/riskClient';
import type {
  CreateLimitBody,
  LimitBreach,
  LimitEventBody,
  LimitMetric,
  LimitScope,
  LimitUsage,
  LimitUsageResponse,
} from '../../api/riskTypes';
import { fmtDate, fmtMoney, fmtNumber } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import { LIMIT_METRIC_LABEL, LIMIT_SCOPE_LABEL, LIMIT_STATUS_LABEL } from './labels';
import './LimitsTab.css';

const SCOPES: LimitScope[] = ['counterparty', 'factor', 'portfolio'];

// Misma tabla que el backend (METRICS_BY_SCOPE): la interfaz solo ofrece combinaciones válidas.
const METRICS_BY_SCOPE: Record<LimitScope, LimitMetric[]> = {
  counterparty: ['pv_exposure'],
  factor: ['dv01', 'fx_delta'],
  portfolio: ['var'],
};

// Claves de factor por métrica: el DV01 es por curva; la delta es de USDMXN.
// Hueco de diseño: el plan dice "curva: TIIE-F/SOFR; USDMXN" sin atar cada clave a su métrica; lo conservador es atarla.
const FACTOR_KEYS: Partial<Record<LimitMetric, string[]>> = {
  dv01: ['TIIE-F', 'SOFR'],
  fx_delta: ['USDMXN'],
};

const FORM_FIELDS = ['scope', 'metric', 'key', 'amount', 'reason'];

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'No se pudo conectar con el backend');
}

/** "Contraparte · Banco A · Exposición (PV positivo neto)"; el portafolio no lleva clave. */
function limitName(scope: LimitScope, key: string, metric: LimitMetric): string {
  const parts = [LIMIT_SCOPE_LABEL[scope]];
  if (scope !== 'portfolio') parts.push(key);
  parts.push(LIMIT_METRIC_LABEL[metric]);
  return parts.join(' · ');
}

const pctText = (pct: number) => `${fmtNumber(pct, 1)} %`;

/** Acciones de una fila: cambio de monto en línea y baja con confirmación. */
function RowActions({
  usage,
  onEvent,
}: {
  usage: LimitUsage;
  onEvent: (id: number, body: LimitEventBody) => Promise<void>;
}) {
  const [mode, setMode] = useState<'change' | 'retire' | null>(null);
  const [amount, setAmount] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);

  const close = () => {
    setMode(null);
    setError(null);
  };

  const run = async (body: LimitEventBody) => {
    setPending(true);
    setError(null);
    try {
      await onEvent(usage.limit_id, body);
      setMode(null);
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setPending(false);
    }
  };

  const saveChange = () => {
    const n = Number(amount);
    if (amount.trim() === '' || !Number.isFinite(n)) {
      setError(new ApiError(400, 'Ingresa un número válido', 'amount'));
      return;
    }
    void run({ type: 'change', amount: n });
  };

  if (mode === 'change') {
    return (
      <div className="lim-actions">
        <input
          type="number"
          step="any"
          className="lim-inline-input"
          aria-label="Nuevo monto (MXN)"
          aria-invalid={error ? true : undefined}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <button type="button" className="lim-btn lim-btn--primary" disabled={pending} onClick={saveChange}>
          Guardar
        </button>
        <button type="button" className="lim-btn" disabled={pending} onClick={close}>
          Cancelar
        </button>
        {error && <span className="lim-field__error">{error.message}</span>}
      </div>
    );
  }

  if (mode === 'retire') {
    return (
      <div className="lim-actions">
        <span>¿Dar de baja este límite?</span>
        <button
          type="button"
          className="lim-btn lim-btn--danger"
          disabled={pending}
          onClick={() => void run({ type: 'retire' })}
        >
          Confirmar baja
        </button>
        <button type="button" className="lim-btn" disabled={pending} onClick={close}>
          Cancelar
        </button>
        {error && <span className="lim-field__error">{error.message}</span>}
      </div>
    );
  }

  return (
    <div className="lim-actions">
      <button
        type="button"
        className="lim-btn"
        onClick={() => {
          setAmount(String(usage.amount));
          setMode('change');
        }}
      >
        Cambiar monto
      </button>
      <button type="button" className="lim-btn" onClick={() => setMode('retire')}>
        Dar de baja
      </button>
    </div>
  );
}

function UsageTable({
  usage,
  onEvent,
}: {
  usage: LimitUsage[];
  onEvent: (id: number, body: LimitEventBody) => Promise<void>;
}) {
  if (usage.length === 0) return <p className="lim-empty">Sin límites vigentes.</p>;
  return (
    <div className="radv-scroll">
      <table className="radv-table">
        <thead>
          <tr>
            <th>Alcance</th>
            <th>Clave</th>
            <th>Métrica</th>
            <th className="num">Monto</th>
            <th className="num">Uso</th>
            <th>Uso del límite</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {usage.map((u) => (
            <tr key={u.limit_id}>
              <td>{LIMIT_SCOPE_LABEL[u.scope]}</td>
              <td>{u.scope === 'portfolio' ? '—' : u.key}</td>
              <td>{LIMIT_METRIC_LABEL[u.metric]}</td>
              <td className="num">{fmtMoney(u.amount, 'MXN')}</td>
              <td className="num">{fmtMoney(u.usage, 'MXN')}</td>
              <td>
                <div className="lim-usage">
                  <div
                    className="radv-bar"
                    data-status={u.status}
                    style={{ '--pct': Math.max(0, Math.min(u.pct, 100)) } as CSSProperties}
                  />
                  <span className="num">{pctText(u.pct)}</span>
                </div>
              </td>
              <td>
                <span className="radv-status" data-status={u.status}>
                  {LIMIT_STATUS_LABEL[u.status]}
                </span>
              </td>
              <td>
                <RowActions usage={u} onEvent={onEvent} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error: string | null;
  children: ReactNode;
}) {
  return (
    <div className="lim-field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error && (
        <span id={`${id}-error`} className="lim-field__error">
          {error}
        </span>
      )}
    </div>
  );
}

function NewLimitForm({ counterparties, onCreated }: { counterparties: string[]; onCreated: () => Promise<void> }) {
  const [scope, setScope] = useState<LimitScope>('counterparty');
  const [metric, setMetric] = useState<LimitMetric>('pv_exposure');
  const [key, setKey] = useState('');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);

  // Métrica y clave vigentes: lo elegido si sigue siendo válido para el alcance; si no, la primera opción.
  const metrics = METRICS_BY_SCOPE[scope];
  const currentMetric = metrics.includes(metric) ? metric : metrics[0];
  const keys = scope === 'counterparty' ? counterparties : scope === 'factor' ? (FACTOR_KEYS[currentMetric] ?? []) : [];
  const currentKey = keys.includes(key) ? key : (keys[0] ?? '');

  const fieldError = (field: string) => (error?.field === field ? error.message : null);
  const generalError = error && !(error.field && FORM_FIELDS.includes(error.field)) ? error : null;
  const invalid = (field: string) => (fieldError(field) ? true : undefined);
  const describedBy = (id: string, field: string) => (fieldError(field) ? `${id}-error` : undefined);

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    const n = Number(amount);
    if (amount.trim() === '' || !Number.isFinite(n)) {
      setError(new ApiError(400, 'Ingresa un número válido', 'amount'));
      return;
    }
    const body: CreateLimitBody = { scope, metric: currentMetric, amount: n };
    if (scope !== 'portfolio') body.key = currentKey;
    if (reason.trim() !== '') body.reason = reason.trim();
    setPending(true);
    setError(null);
    try {
      await createLimit(body);
      setAmount('');
      setReason('');
      await onCreated();
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="radv-card" aria-labelledby="lim-new-title">
      <h2 id="lim-new-title">Nuevo límite</h2>
      <form className="lim-form" onSubmit={(ev) => void submit(ev)} noValidate>
        <Field id="lim-scope" label="Alcance" error={fieldError('scope')}>
          <select
            id="lim-scope"
            className="lim-control"
            value={scope}
            aria-invalid={invalid('scope')}
            aria-describedby={describedBy('lim-scope', 'scope')}
            onChange={(e) => setScope(e.target.value as LimitScope)}
          >
            {SCOPES.map((s) => (
              <option key={s} value={s}>
                {LIMIT_SCOPE_LABEL[s]}
              </option>
            ))}
          </select>
        </Field>
        <Field id="lim-metric" label="Métrica" error={fieldError('metric')}>
          <select
            id="lim-metric"
            className="lim-control"
            value={currentMetric}
            aria-invalid={invalid('metric')}
            aria-describedby={describedBy('lim-metric', 'metric')}
            onChange={(e) => setMetric(e.target.value as LimitMetric)}
          >
            {metrics.map((m) => (
              <option key={m} value={m}>
                {LIMIT_METRIC_LABEL[m]}
              </option>
            ))}
          </select>
        </Field>
        {scope !== 'portfolio' && (
          <Field id="lim-key" label="Clave" error={fieldError('key')}>
            <select
              id="lim-key"
              className="lim-control"
              value={currentKey}
              aria-invalid={invalid('key')}
              aria-describedby={describedBy('lim-key', 'key')}
              onChange={(e) => setKey(e.target.value)}
            >
              {keys.length === 0 && <option value="">Sin opciones</option>}
              {keys.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field id="lim-amount" label="Monto (MXN)" error={fieldError('amount')}>
          <input
            id="lim-amount"
            className="lim-control lim-control--num"
            type="number"
            step="any"
            value={amount}
            aria-invalid={invalid('amount')}
            aria-describedby={describedBy('lim-amount', 'amount')}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
        <Field id="lim-reason" label="Motivo" error={fieldError('reason')}>
          <input
            id="lim-reason"
            className="lim-control"
            type="text"
            value={reason}
            aria-invalid={invalid('reason')}
            aria-describedby={describedBy('lim-reason', 'reason')}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <div className="lim-form__submit">
          <button type="submit" className="lim-btn lim-btn--primary" disabled={pending}>
            Agregar límite
          </button>
        </div>
      </form>
      {scope === 'counterparty' && counterparties.length === 0 && (
        <p className="radv-note radv-note--warn" role="status">
          No hay contrapartes: se toman de las operaciones registradas.
        </p>
      )}
      {generalError && (
        <p className="radv-note radv-note--error" role="alert">
          {generalError.message}
        </p>
      )}
    </section>
  );
}

function BreachLog({ breaches, error }: { breaches: LimitBreach[] | null; error: ApiError | null }) {
  return (
    <section className="radv-card" aria-labelledby="lim-log-title">
      <h2 id="lim-log-title">Bitácora de excesos</h2>
      {error && (
        <p className="radv-note radv-note--error" role="alert">
          {error.message}
        </p>
      )}
      {breaches && breaches.length === 0 && <p className="lim-empty">Sin excesos registrados.</p>}
      {breaches && breaches.length > 0 && (
        <div className="radv-scroll">
          <table className="radv-table">
            <thead>
              <tr>
                <th>Fecha de valuación</th>
                <th>Snapshot</th>
                <th>Límite</th>
                <th className="num">Monto</th>
                <th className="num">Uso</th>
                <th className="num">% del límite</th>
              </tr>
            </thead>
            <tbody>
              {breaches.map((b) => (
                <tr key={b.id}>
                  <td>{fmtDate(b.as_of)}</td>
                  <td>{b.snapshot}</td>
                  <td>{limitName(b.scope, b.key, b.metric)}</td>
                  <td className="num">{fmtMoney(b.amount, 'MXN')}</td>
                  <td className="num">{fmtMoney(b.usage, 'MXN')}</td>
                  <td className="num">{pctText(b.pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function LimitsTab() {
  const { snapshotId } = useSnapshot();
  const [usage, setUsage] = useState<LimitUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [review, setReview] = useState<LimitBreach[] | null>(null);
  const [checking, setChecking] = useState(false);
  const [breaches, setBreaches] = useState<LimitBreach[] | null>(null);
  const [breachError, setBreachError] = useState<ApiError | null>(null);
  const [counterparties, setCounterparties] = useState<string[]>([]);
  // Solo la última carga de uso escribe estado (una respuesta lenta de otro snapshot no pisa a la vigente).
  const ticket = useRef(0);

  const loadUsage = useCallback(async () => {
    const mine = ++ticket.current;
    setLoading(true);
    try {
      const res = await limitUsage(snapshotId);
      if (mine === ticket.current) {
        setUsage(res);
        setLoadError(null);
      }
    } catch (e) {
      if (mine === ticket.current) {
        setUsage(null);
        setLoadError(toApiError(e));
      }
    } finally {
      if (mine === ticket.current) setLoading(false);
    }
  }, [snapshotId]);

  const loadBreaches = useCallback(async () => {
    try {
      setBreaches(await listBreaches());
      setBreachError(null);
    } catch (e) {
      setBreachError(toApiError(e));
    }
  }, []);

  useEffect(() => {
    setReview(null);
    void loadUsage();
    return () => {
      ticket.current++;
    };
  }, [loadUsage]);

  useEffect(() => {
    void loadBreaches();
  }, [loadBreaches]);

  useEffect(() => {
    let live = true;
    listTrades().then(
      (trades) => {
        if (live) setCounterparties([...new Set(trades.map((t) => t.counterparty))].sort());
      },
      () => {
        // Sin operaciones no hay contrapartes que ofrecer; el formulario lo avisa.
      },
    );
    return () => {
      live = false;
    };
  }, []);

  const onEvent = useCallback(
    async (id: number, body: LimitEventBody) => {
      await addLimitEvent(id, body);
      await loadUsage();
    },
    [loadUsage],
  );

  const runCheck = async () => {
    const mine = ++ticket.current;
    setChecking(true);
    setLoadError(null);
    try {
      const res = await checkLimits(snapshotId);
      if (mine === ticket.current) {
        setUsage(res);
        setReview(res.new_breaches);
      }
      await loadBreaches();
    } catch (e) {
      if (mine === ticket.current) setLoadError(toApiError(e));
    } finally {
      setChecking(false);
    }
  };

  return (
    <>
      <section className={`radv-card${loading ? ' is-loading' : ''}`} aria-labelledby="lim-usage-title">
        <div className="lim-head">
          <h2 id="lim-usage-title">Uso de límites</h2>
          <button type="button" className="lim-btn lim-btn--primary" disabled={checking} onClick={() => void runCheck()}>
            Revisar límites
          </button>
        </div>
        {loadError && (
          <p className="radv-note radv-note--error" role="alert">
            {loadError.message}
          </p>
        )}
        {review && (
          <div className="radv-note radv-note--warn" role="status">
            {review.length === 0 ? (
              'Sin excesos nuevos'
            ) : (
              <>
                Excesos nuevos:
                <ul className="lim-new">
                  {review.map((b) => (
                    <li key={b.id}>
                      {limitName(b.scope, b.key, b.metric)}: {fmtMoney(b.usage, 'MXN')} de {fmtMoney(b.amount, 'MXN')} (
                      {pctText(b.pct)})
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
        {usage && (
          <>
            <UsageTable usage={usage.usage} onEvent={onEvent} />
            {usage.errors.length > 0 && (
              <p className="radv-note radv-note--warn" role="status">
                Operaciones excluidas del cálculo: {usage.errors.map((e) => `#${e.id} (${e.error})`).join('; ')}
              </p>
            )}
            <p className="lim-foot">
              Valuación al {fmtDate(usage.as_of)}. Alerta desde {pctText(usage.thresholds.alert_pct)} del monto; exceso
              por encima de {pctText(usage.thresholds.breach_pct)}.
            </p>
          </>
        )}
      </section>
      <NewLimitForm counterparties={counterparties} onCreated={loadUsage} />
      <BreachLog breaches={breaches} error={breachError} />
    </>
  );
}
