import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { ApiError, listTrades } from '../../api/client';
import { createScenarioSet, listScenarioSets, retireScenarioSet, runScenarioSet } from '../../api/riskClient';
import type { LibraryScenario, ScenarioSet, SetScenariosResponse, Shock } from '../../api/riskTypes';
import type { ScenarioSpec, Trade } from '../../api/types';
import { fmtNumber } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import './ScenarioLibraryTab.css';

const CURVES = ['TIIE-F', 'SOFR'] as const;
type Curve = (typeof CURVES)[number];
type RowKind = 'parallel' | 'steepener' | 'fx_spot';

const KIND_LABEL: Record<RowKind, string> = {
  parallel: 'Paralelo',
  steepener: 'Steepener',
  fx_spot: 'USDMXN spot',
};
const KINDS: RowKind[] = ['parallel', 'steepener', 'fx_spot'];

const FORM_FIELDS = ['name', 'scenarios'];

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'No se pudo conectar con el backend');
}

/* ---------- Texto legible de los choques ---------- */

/** Número sin ceros sobrantes ("100", "12.5"); el signo lo pone quien llama. */
function plain(v: number): string {
  return String(Number(Math.abs(v).toFixed(4)));
}

function signed(v: number): string {
  return `${v < 0 ? '−' : '+'}${plain(v)}`;
}

/** "TIIE-F +100 pb", "TIIE-F steepener +25 pb", "USDMXN +25 %". */
function shockText(s: Shock | ScenarioSpec): string {
  if (s.type === 'fx_spot') return `USDMXN ${signed(s.pct)} %`;
  if (s.type === 'steepener') return `${s.curve} steepener ${signed(s.bp)} pb`;
  return `${s.curve} ${signed(s.bp)} pb`;
}

/** Un escenario combinado une sus choques con " · ". */
function scenarioText(sc: LibraryScenario): string {
  return sc.type === 'combined' ? sc.shocks.map(shockText).join(' · ') : shockText(sc);
}

/* ---------- Un conjunto de la lista ---------- */

function SetItem({
  set,
  running,
  onRun,
  onRetire,
}: {
  set: ScenarioSet;
  running: boolean;
  onRun: (set: ScenarioSet) => Promise<void>;
  onRetire: (set: ScenarioSet) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);

  const act = async (fn: () => Promise<void>) => {
    setPending(true);
    setError(null);
    try {
      await fn();
      setConfirming(false);
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <li className="scn-set">
      <div className="scn-set__head">
        <h3>{set.name}</h3>
        {set.builtin && <span className="scn-badge">De fábrica</span>}
        {set.approximation && <span className="scn-badge scn-badge--warn">Aproximación histórica</span>}
      </div>
      {set.description && <p className="scn-set__desc">{set.description}</p>}
      <ul className="scn-detail">
        {set.scenarios.map((sc, i) => {
          const text = scenarioText(sc);
          // Si el nombre ya es el choque ("TIIE-F +50 pb") no se repite.
          return (
            <li key={`${i}-${sc.name}`}>
              {text === sc.name ? (
                <span className="scn-detail__shock scn-detail__solo">{text}</span>
              ) : (
                <>
                  <span className="scn-detail__name">{sc.name}</span>
                  <span className="scn-detail__shock">{text}</span>
                </>
              )}
            </li>
          );
        })}
      </ul>
      <div className="scn-actions">
        {confirming ? (
          <>
            <span>¿Dar de baja este conjunto?</span>
            <button
              type="button"
              className="scn-btn scn-btn--danger"
              disabled={pending}
              onClick={() => void act(() => onRetire(set))}
            >
              Confirmar baja
            </button>
            <button
              type="button"
              className="scn-btn"
              disabled={pending}
              onClick={() => {
                setConfirming(false);
                setError(null);
              }}
            >
              Cancelar
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="scn-btn scn-btn--primary"
              disabled={pending || running}
              aria-label={`Correr ${set.name}`}
              onClick={() => void act(() => onRun(set))}
            >
              Correr
            </button>
            {!set.builtin && (
              <button
                type="button"
                className="scn-btn"
                aria-label={`Dar de baja ${set.name}`}
                onClick={() => setConfirming(true)}
              >
                Dar de baja
              </button>
            )}
          </>
        )}
      </div>
      {error && (
        <p className="radv-note radv-note--error" role="alert">
          {error.message}
        </p>
      )}
    </li>
  );
}

/* ---------- Resultado de una corrida ---------- */

interface RunResult {
  set: string;
  snapshot: string;
  res: SetScenariosResponse;
  trades: Trade[];
}

const signClass = (v: number | null | undefined) => (v == null || v === 0 ? '' : v > 0 ? 'scn-pos' : 'scn-neg');

function ResultTable({ result }: { result: RunResult }) {
  const { res, trades } = result;
  const byId = new Map(trades.map((t) => [t.id, t]));
  const ids: number[] = [];
  for (const sc of res.scenarios) for (const t of sc.trades) if (!ids.includes(t.id)) ids.push(t.id);

  return (
    <div className="radv-scroll">
      <table className="radv-table">
        <thead>
          <tr>
            <th>Operación</th>
            {res.scenarios.map((sc, i) => (
              <th key={`${i}-${sc.name}`} className="num">
                {sc.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ids.map((id) => {
            const t = byId.get(id);
            return (
              <tr key={id}>
                <td>{t ? `#${id} ${t.product} · ${t.counterparty}` : `#${id}`}</td>
                {res.scenarios.map((sc, i) => {
                  const cell = sc.trades.find((x) => x.id === id);
                  const v = cell?.pnl_mxn ?? null;
                  return (
                    <td key={i} className={`num ${signClass(v)}`} title={cell?.error ?? undefined}>
                      {v == null ? 'n/d' : fmtNumber(v, 0)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {ids.length === 0 && (
            <tr>
              <td colSpan={res.scenarios.length + 1} className="scn-empty">
                Sin operaciones en el portafolio
              </td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr className="scn-total">
            <th scope="row">Total</th>
            {res.scenarios.map((sc, i) => (
              <td key={i} className={`num ${signClass(sc.total_mxn)}`}>
                {fmtNumber(sc.total_mxn, 0)}
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/* ---------- Formulario Nuevo conjunto ---------- */

interface FormRow {
  key: number;
  name: string;
  kind: RowKind;
  curve: Curve;
  value: string;
}

function Field({ id, label, error, children }: { id: string; label: string; error: string | null; children: ReactNode }) {
  return (
    <div className="scn-field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error && (
        <span id={`${id}-error`} className="scn-field__error">
          {error}
        </span>
      )}
    </div>
  );
}

function NewSetForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const nextKey = useRef(1);
  const blankRow = (): FormRow => ({ key: nextKey.current++, name: '', kind: 'parallel', curve: 'TIIE-F', value: '' });

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rows, setRows] = useState<FormRow[]>(() => [blankRow()]);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);

  const fieldError = (field: string) => (error?.field === field ? error.message : null);
  const generalError = error && !(error.field && FORM_FIELDS.includes(error.field)) ? error : null;

  const patchRow = (key: number, patch: Partial<FormRow>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    const scenarios: LibraryScenario[] = [];
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      const n = Number(r.value);
      if (r.value.trim() === '' || !Number.isFinite(n)) {
        setError(new ApiError(400, `Escenario ${i + 1}: ingresa un número válido`, 'scenarios'));
        return;
      }
      const label = r.name.trim();
      scenarios.push(
        r.kind === 'fx_spot'
          ? { name: label, type: 'fx_spot', pct: n }
          : { name: label, type: r.kind, curve: r.curve, bp: n },
      );
    }
    const body: Parameters<typeof createScenarioSet>[0] = { name: name.trim(), scenarios };
    if (description.trim() !== '') body.description = description.trim();
    setPending(true);
    setError(null);
    try {
      await createScenarioSet(body);
      setName('');
      setDescription('');
      setRows([blankRow()]);
      await onCreated();
    } catch (e) {
      setError(toApiError(e));
    } finally {
      setPending(false);
    }
  };

  const scenariosError = fieldError('scenarios');

  return (
    <section className="radv-card" aria-labelledby="scn-new-title">
      <h2 id="scn-new-title">Nuevo conjunto</h2>
      <form className="scn-form" onSubmit={(ev) => void submit(ev)} noValidate>
        <div className="scn-form__top">
          <Field id="scn-name" label="Nombre" error={fieldError('name')}>
            <input
              id="scn-name"
              className="scn-control"
              type="text"
              value={name}
              aria-invalid={fieldError('name') ? true : undefined}
              aria-describedby={fieldError('name') ? 'scn-name-error' : undefined}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field id="scn-desc" label="Descripción" error={null}>
            <input
              id="scn-desc"
              className="scn-control"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Field>
        </div>

        <fieldset className="scn-rows" aria-describedby={scenariosError ? 'scn-rows-error' : undefined}>
          <legend>Escenarios</legend>
          {rows.map((r, i) => {
            const n = i + 1;
            return (
              <div key={r.key} className="scn-row" role="group" aria-label={`Escenario ${n}`}>
                <div className="scn-field">
                  <label htmlFor={`scn-row-${r.key}-name`}>Nombre del escenario {n}</label>
                  <input
                    id={`scn-row-${r.key}-name`}
                    className="scn-control"
                    type="text"
                    value={r.name}
                    onChange={(e) => patchRow(r.key, { name: e.target.value })}
                  />
                </div>
                <div className="scn-field">
                  <label htmlFor={`scn-row-${r.key}-kind`}>Tipo del escenario {n}</label>
                  <select
                    id={`scn-row-${r.key}-kind`}
                    className="scn-control"
                    value={r.kind}
                    onChange={(e) => patchRow(r.key, { kind: e.target.value as RowKind })}
                  >
                    {KINDS.map((k) => (
                      <option key={k} value={k}>
                        {KIND_LABEL[k]}
                      </option>
                    ))}
                  </select>
                </div>
                {r.kind !== 'fx_spot' && (
                  <div className="scn-field">
                    <label htmlFor={`scn-row-${r.key}-curve`}>Curva del escenario {n}</label>
                    <select
                      id={`scn-row-${r.key}-curve`}
                      className="scn-control"
                      value={r.curve}
                      onChange={(e) => patchRow(r.key, { curve: e.target.value as Curve })}
                    >
                      {CURVES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="scn-field">
                  <label htmlFor={`scn-row-${r.key}-value`}>{r.kind === 'fx_spot' ? 'Variación (%)' : 'Choque (pb)'} del escenario {n}</label>
                  <input
                    id={`scn-row-${r.key}-value`}
                    className="scn-control scn-control--num"
                    type="number"
                    step="any"
                    value={r.value}
                    onChange={(e) => patchRow(r.key, { value: e.target.value })}
                  />
                </div>
                <button
                  type="button"
                  className="scn-btn"
                  aria-label={`Quitar escenario ${n}`}
                  disabled={rows.length === 1}
                  onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
                >
                  Quitar
                </button>
              </div>
            );
          })}
          {scenariosError && (
            <span id="scn-rows-error" className="scn-field__error">
              {scenariosError}
            </span>
          )}
          <div>
            <button type="button" className="scn-btn" onClick={() => setRows((rs) => [...rs, blankRow()])}>
              Agregar escenario
            </button>
          </div>
        </fieldset>

        {generalError && (
          <p className="radv-note radv-note--error" role="alert">
            {generalError.message}
          </p>
        )}
        <div>
          <button type="submit" className="scn-btn scn-btn--primary" disabled={pending}>
            Crear conjunto
          </button>
        </div>
      </form>
    </section>
  );
}

/* ---------- Pestaña ---------- */

export function ScenarioLibraryTab() {
  const { snapshotId } = useSnapshot();
  const [sets, setSets] = useState<ScenarioSet[] | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  // Solo la última corrida escribe resultado (otra corrida o un cambio de snapshot invalidan la anterior).
  const ticket = useRef(0);

  const reload = useCallback(async () => {
    try {
      setSets(await listScenarioSets());
      setLoadError(null);
    } catch (e) {
      setLoadError(toApiError(e));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Un resultado es de un snapshot concreto: al cambiar de snapshot se descarta en vez de mostrarlo viejo.
  useEffect(() => {
    ticket.current++;
    setResult(null);
    setRunning(false);
  }, [snapshotId]);

  const run = useCallback(
    async (set: ScenarioSet) => {
      const mine = ++ticket.current;
      setRunning(true);
      try {
        const [res, trades] = await Promise.all([runScenarioSet(snapshotId, set.name), listTrades()]);
        if (mine === ticket.current) setResult({ set: set.name, snapshot: snapshotId, res, trades });
      } finally {
        if (mine === ticket.current) setRunning(false);
      }
    },
    [snapshotId],
  );

  const retire = useCallback(
    async (set: ScenarioSet) => {
      if (set.id == null) return;
      await retireScenarioSet(set.id);
      setResult((r) => (r?.set === set.name ? null : r));
      await reload();
    },
    [reload],
  );

  return (
    <>
      <section className="radv-card" aria-labelledby="scn-list-title">
        <h2 id="scn-list-title">Conjuntos de escenarios</h2>
        {loadError && (
          <p className="radv-note radv-note--error" role="alert">
            {loadError.message}
          </p>
        )}
        {sets && sets.length === 0 && <p className="scn-empty">Sin conjuntos.</p>}
        {sets && sets.length > 0 && (
          <ul className="scn-sets">
            {sets.map((s) => (
              <SetItem key={s.id ?? `fabrica-${s.name}`} set={s} running={running} onRun={run} onRetire={retire} />
            ))}
          </ul>
        )}
      </section>

      {result && (
        <section className="radv-card scn-result" aria-labelledby="scn-result-title">
          <h2 id="scn-result-title">Corrida: {result.set}</h2>
          <ResultTable result={result} />
          <p className="scn-foot">
            P&amp;L en MXN por operación frente al snapshot base ({result.snapshot}). Las celdas n/d no se pudieron
            valuar: pasa el cursor para ver el motivo.
          </p>
        </section>
      )}

      <NewSetForm onCreated={reload} />
    </>
  );
}
