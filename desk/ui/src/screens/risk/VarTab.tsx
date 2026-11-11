import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, riskVar } from '../../api/client';
import { riskVarHistorical } from '../../api/riskClient';
import type { HistVarResponse } from '../../api/riskTypes';
import type { TradeError, VarResponse } from '../../api/types';
import { fmtDate, fmtMoney, fmtNumber, fmtRate } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import { HISTORY_SOURCE_LABEL } from './labels';
import './VarTab.css';

type Field = 'horizon_days' | 'confidence' | 'window_days';

interface Inputs {
  horizon: string;
  confidence: string;
  window: string;
}

const DEFAULTS: Inputs = { horizon: '10', confidence: '99', window: '250' };

const FIELD_OF: Record<keyof Inputs, Field> = {
  horizon: 'horizon_days',
  confidence: 'confidence',
  window: 'window_days',
};

interface Params {
  horizon: number;
  confidence: number;
  window: number;
}

interface Result<T> {
  data: T | null;
  error: ApiError | null;
}

interface State {
  loading: boolean;
  parametric: Result<VarResponse>;
  historical: Result<HistVarResponse>;
  fieldErrors: Partial<Record<Field, string>>;
}

const API_FIELDS: string[] = Object.values(FIELD_OF);

const NO_RESULT = { data: null, error: null };

const UNIT_LABEL: Record<string, string> = { bp: 'pb', ret: 'rend.' };

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'No se pudo conectar con el backend');
}

async function settle<T>(call: () => Promise<T>): Promise<Result<T>> {
  try {
    return { data: await call(), error: null };
  } catch (e) {
    return { data: null, error: toApiError(e) };
  }
}

/** Lee los tres campos; si alguno no es un número devuelve el mensaje de cada uno (no se llama a la API). */
function parseInputs(inputs: Inputs): { params: Params } | { errors: Partial<Record<Field, string>> } {
  const errors: Partial<Record<Field, string>> = {};
  const values = {} as Params;
  for (const key of Object.keys(FIELD_OF) as (keyof Inputs)[]) {
    const text = inputs[key];
    const n = Number(text);
    if (text.trim() === '' || !Number.isFinite(n)) errors[FIELD_OF[key]] = 'Ingresa un número válido';
    else values[key] = n;
  }
  return Object.keys(errors).length > 0 ? { errors } : { params: values };
}

function fmtVol(v: number, unit: string): string {
  return unit === 'ret' ? fmtRate(v) : `${fmtNumber(v, 2)} ${UNIT_LABEL[unit] ?? unit}`;
}

function varCaption(label: string, confidence: number, horizon: number): string {
  return `${label} ${parseFloat((confidence * 100).toFixed(4))} % a ${horizon} ${horizon === 1 ? 'día' : 'días'}`;
}

/** Un 400 que apunta a uno de los tres campos del formulario: su mensaje va bajo ese campo. */
function isFieldError(error: ApiError | null): boolean {
  return error?.status === 400 && error.field !== null && API_FIELDS.includes(error.field);
}

const signed = (v: number, text: string) => (v > 0 ? `+${text}` : text);

function ExcludedNote({ errors }: { errors: TradeError[] }) {
  if (errors.length === 0) return null;
  return (
    <p className="radv-note radv-note--warn" role="status">
      Operaciones excluidas: {errors.map((e) => `#${e.id} (${e.error})`).join('; ')}
    </p>
  );
}

function ParametricCard({ result, loading }: { result: Result<VarResponse>; loading: boolean }) {
  const { data, error } = result;
  return (
    <section className={`radv-card${loading ? ' is-loading' : ''}`} aria-labelledby="vartab-param-title">
      <h2 id="vartab-param-title">Paramétrico</h2>
      {error && !isFieldError(error) && (
        <p className="radv-note radv-note--error" role="alert">
          {error.message}
        </p>
      )}
      {isFieldError(error) && <p className="radv-note">Sin resultado: corrige el campo señalado.</p>}
      {data && (
        <>
          <div className="radv-tiles">
            <div className="radv-tile">
              <span className="vartab-caption">{varCaption('VaR', data.confidence, data.horizon_days)}</span>
              <span className="vartab-value num">{fmtMoney(data.var_mxn, 'MXN')}</span>
            </div>
          </div>
          <div className="radv-scroll">
            <table className="radv-table">
              <thead>
                <tr>
                  <th>Factor</th>
                  <th className="num">Exposición</th>
                  <th className="num">Vol. diaria</th>
                  <th className="num">VaR individual</th>
                </tr>
              </thead>
              <tbody>
                {data.factors.map((f) => (
                  <tr key={f.factor}>
                    <td>{f.factor}</td>
                    <td className="num">{fmtNumber(f.exposure_mxn, 2)}</td>
                    <td className="num">{fmtVol(f.daily_vol, f.unit)}</td>
                    <td className="num">{fmtNumber(f.var_mxn, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="vartab-foot">
            Exposición y VaR en MXN. Exposición = P&amp;L ante +1 pb paralelo (tasas) o ante un rendimiento relativo
            unitario del spot (USDMXN); volatilidades y correlaciones del snapshot.
          </p>
          <ExcludedNote errors={data.errors} />
        </>
      )}
    </section>
  );
}

function HistoricalCard({ result, loading }: { result: Result<HistVarResponse>; loading: boolean }) {
  const { data, error } = result;
  return (
    <section className={`radv-card${loading ? ' is-loading' : ''}`} aria-labelledby="vartab-hist-title">
      <h2 id="vartab-hist-title">Histórico</h2>
      {/* 409: no hay historia suficiente; no es un fallo, es un aviso (la paramétrica sigue visible). */}
      {error?.status === 409 && (
        <p className="radv-note radv-note--warn" role="status">
          {error.message}
        </p>
      )}
      {error && error.status !== 409 && !isFieldError(error) && (
        <p className="radv-note radv-note--error" role="alert">
          {error.message}
        </p>
      )}
      {isFieldError(error) && <p className="radv-note">Sin resultado: corrige el campo señalado.</p>}
      {data && (
        <>
          <div className="radv-tiles">
            <div className="radv-tile">
              <span className="vartab-caption">{varCaption('VaR', data.confidence, data.horizon_days)}</span>
              <span className="vartab-value num">{fmtMoney(data.var_mxn, 'MXN')}</span>
            </div>
            <div className="radv-tile">
              <span className="vartab-caption">Déficit esperado (ES)</span>
              <span className="vartab-value num">{fmtMoney(data.es_mxn, 'MXN')}</span>
            </div>
            <div className="radv-tile">
              <span className="vartab-caption">Peor día (P&amp;L de 1 día)</span>
              <span className="vartab-value num">{fmtMoney(data.worst_day.pnl_mxn, 'MXN')}</span>
              <span className="vartab-sub">{fmtDate(data.worst_day.date)}</span>
            </div>
          </div>
          <div className="radv-scroll">
            <table className="radv-table">
              <thead>
                <tr>
                  <th>Factor</th>
                  <th className="num">Exposición</th>
                </tr>
              </thead>
              <tbody>
                {data.factors.map((f) => (
                  <tr key={f.factor}>
                    <td>{f.factor}</td>
                    <td className="num">{fmtNumber(f.exposure_mxn, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 className="vartab-subtitle">Historia usada</h3>
          <dl className="vartab-history">
            <dt>Fuente</dt>
            <dd>{HISTORY_SOURCE_LABEL[data.history.source]}</dd>
            <dt>Descripción</dt>
            <dd>{data.history.label}</dd>
            <dt>Rango</dt>
            <dd>
              {fmtDate(data.history.from)} – {fmtDate(data.history.to)}
            </dd>
            <dt>Observaciones</dt>
            <dd className="num">{fmtNumber(data.history.observations, 0)}</dd>
          </dl>
          <p className="vartab-foot">
            Revaluación por sensibilidades (delta): P&amp;L diario = exposiciones × cambios históricos; percentil
            empírico, escalado por la raíz del horizonte.
          </p>
          <ExcludedNote errors={data.errors} />
        </>
      )}
    </section>
  );
}

function Difference({ parametric, historical }: { parametric: VarResponse; historical: HistVarResponse }) {
  const diff = historical.var_mxn - parametric.var_mxn;
  // Signo explícito solo en positivos: "MXN +1.00" / "MXN -1.00" / "MXN 0.00".
  const money = diff > 0 ? `MXN +${fmtNumber(diff, 2)}` : fmtMoney(diff, 'MXN');
  const pct = parametric.var_mxn !== 0 ? (diff / parametric.var_mxn) * 100 : null;
  return (
    <section className="radv-card" aria-labelledby="vartab-diff-title">
      <h2 id="vartab-diff-title">Diferencia</h2>
      <div className="radv-tile vartab-diff">
        <span className="vartab-caption">Histórico − Paramétrico</span>
        <span className="vartab-value num">
          {money}
          {pct !== null && ` (${signed(pct, `${fmtNumber(pct, 2)} %`)})`}
        </span>
      </div>
    </section>
  );
}

export function VarTab() {
  const { snapshotId } = useSnapshot();
  const [inputs, setInputs] = useState<Inputs>(DEFAULTS);
  // Lo último que se calculó: cambiar un campo no recalcula hasta pulsar «Calcular»; cambiar de snapshot sí.
  const [applied, setApplied] = useState<Inputs>(DEFAULTS);
  const [state, setState] = useState<State>({ loading: true, parametric: NO_RESULT, historical: NO_RESULT, fieldErrors: {} });
  const ticket = useRef(0);

  useEffect(() => {
    const mine = ++ticket.current;
    const parsed = parseInputs(applied);
    if ('errors' in parsed) {
      setState({ loading: false, parametric: NO_RESULT, historical: NO_RESULT, fieldErrors: parsed.errors });
      return;
    }
    const { horizon, confidence, window } = parsed.params;
    // El campo viaja en % y la API recibe el decimal (sin ruido de punto flotante).
    const level = Number((confidence / 100).toPrecision(12));
    setState((s) => ({ ...s, loading: true, fieldErrors: {} }));
    Promise.all([
      settle(() => riskVar(snapshotId, horizon, level)),
      settle(() => riskVarHistorical(snapshotId, { horizon_days: horizon, confidence: level, window_days: window })),
    ]).then(([parametric, historical]) => {
      if (mine !== ticket.current) return;
      const fieldErrors: Partial<Record<Field, string>> = {};
      for (const r of [parametric, historical]) {
        // El 409 de historia corta no es un campo mal escrito: es un aviso de la tarjeta histórica.
        if (r.error && isFieldError(r.error)) {
          const field = r.error.field as Field;
          if (!fieldErrors[field]) fieldErrors[field] = r.error.message;
        }
      }
      setState({ loading: false, parametric, historical, fieldErrors });
    });
    return () => {
      ticket.current++;
    };
  }, [snapshotId, applied]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setApplied({ ...inputs });
  };

  const set = (key: keyof Inputs) => (e: { target: { value: string } }) =>
    setInputs((cur) => ({ ...cur, [key]: e.target.value }));

  const fields: { key: keyof Inputs; id: string; label: string }[] = [
    { key: 'horizon', id: 'vartab-horizon', label: 'Horizonte (días)' },
    { key: 'confidence', id: 'vartab-confidence', label: 'Confianza (%)' },
    { key: 'window', id: 'vartab-window', label: 'Ventana (días)' },
  ];

  return (
    <div className="vartab">
      <form className="radv-card vartab-form" onSubmit={submit}>
        {fields.map(({ key, id, label }) => {
          const message = state.fieldErrors[FIELD_OF[key]];
          return (
            <div className="vartab-field" key={key}>
              <label htmlFor={id}>{label}</label>
              <input
                id={id}
                type="number"
                step="any"
                value={inputs[key]}
                aria-invalid={message ? true : undefined}
                aria-describedby={message ? `${id}-error` : undefined}
                onChange={set(key)}
              />
              {message && (
                <span className="vartab-field__error" id={`${id}-error`}>
                  {message}
                </span>
              )}
            </div>
          );
        })}
        <button type="submit" className="vartab-submit" disabled={state.loading}>
          Calcular
        </button>
      </form>
      <div className="radv-grid2">
        <ParametricCard result={state.parametric} loading={state.loading} />
        <HistoricalCard result={state.historical} loading={state.loading} />
      </div>
      {state.parametric.data && state.historical.data && (
        <Difference parametric={state.parametric.data} historical={state.historical.data} />
      )}
    </div>
  );
}
