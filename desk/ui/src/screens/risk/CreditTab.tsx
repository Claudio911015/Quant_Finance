import { useEffect, useRef, useState, type FormEvent } from 'react';
import type { EChartsCoreOption } from 'echarts/core';
import { ApiError } from '../../api/client';
import { creditExposure, listCreditParams, setCreditParams } from '../../api/riskClient';
import type { CreditCounterparty, CreditExposureResponse, CreditParams } from '../../api/riskTypes';
import { EChart, cssColor } from '../../components/EChart';
import { fmtDate, fmtMoney, fmtNumber, fmtRate } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import './CreditTab.css';

type Field = 'hazard_rate' | 'recovery';

interface Inputs {
  hazard: string;
  recovery: string;
}

const FIELD_OF: Record<keyof Inputs, Field> = { hazard: 'hazard_rate', recovery: 'recovery' };

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'No se pudo conectar con el backend');
}

/** Decimal de la API (0.01) como texto del campo en % ("1"), sin ruido de punto flotante. */
const toPercentText = (dec: number) => String(Number((dec * 100).toPrecision(12)));

/** Lo que se teclea en % viaja como decimal. */
const toDecimal = (pct: number) => Number((pct / 100).toPrecision(12));

/**
 * Opción de la gráfica de perfil: EE y PFE de una contraparte contra fecha, en MXN. Función pura (sin ECharts)
 * para probarla sin canvas. `pfeQuantile` solo rotula la leyenda ("PFE 95 %").
 */
export function profileOption(cp: CreditCounterparty, pfeQuantile?: number): EChartsCoreOption {
  const dates = cp.profile.map((p) => fmtDate(p.date));
  const pfeName = pfeQuantile === undefined ? 'PFE' : `PFE ${parseFloat((pfeQuantile * 100).toFixed(4))} %`;
  const axis = {
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    axisLabel: { color: cssColor('--text-dim') },
  };
  return {
    animation: false,
    grid: { left: 64, right: 16, top: 32, bottom: 40 },
    legend: { top: 0, right: 0, textStyle: { color: cssColor('--text-dim') } },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => fmtMoney(v, 'MXN'),
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
    },
    xAxis: { type: 'category', data: dates, ...axis },
    yAxis: {
      type: 'value',
      axisLabel: { color: cssColor('--text-dim'), formatter: (v: number) => `${fmtNumber(v / 1e6, 1)} M` },
      axisLine: axis.axisLine,
      splitLine: { lineStyle: { color: cssColor('--border') } },
    },
    series: [
      {
        name: 'EE',
        type: 'line',
        data: cp.profile.map((p) => p.ee_mxn),
        symbolSize: 4,
        lineStyle: { color: cssColor('--accent'), width: 2 },
        itemStyle: { color: cssColor('--accent') },
      },
      {
        name: pfeName,
        type: 'line',
        data: cp.profile.map((p) => p.pfe_mxn),
        symbolSize: 4,
        lineStyle: { color: cssColor('--warn'), width: 2 },
        itemStyle: { color: cssColor('--warn') },
      },
    ],
  };
}

interface ExposureState {
  loading: boolean;
  data: CreditExposureResponse | null;
  error: ApiError | null;
}

function CounterpartiesCard({
  data,
  selected,
  onSelect,
}: {
  data: CreditExposureResponse;
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  return (
    <section className="radv-card" aria-labelledby="credittab-cps-title">
      <h2 id="credittab-cps-title">Contrapartes</h2>
      {data.counterparties.length === 0 ? (
        <p className="radv-note">No hay contrapartes con operaciones vivas en este snapshot.</p>
      ) : (
        <div className="radv-scroll">
          <table className="radv-table">
            <thead>
              <tr>
                <th>Contraparte</th>
                <th className="num">PV cubierto</th>
                <th className="num">CVA</th>
                <th className="num">Prob. de incumplimiento anual</th>
                <th className="num">Recuperación</th>
              </tr>
            </thead>
            <tbody>
              {data.counterparties.map((cp) => (
                <tr key={cp.counterparty} data-selected={cp.counterparty === selected ? 'true' : undefined}>
                  <td>
                    <button
                      type="button"
                      className="credittab-pick"
                      aria-pressed={cp.counterparty === selected}
                      onClick={() => onSelect(cp.counterparty)}
                    >
                      {cp.counterparty}
                    </button>
                    {cp.assumed && (
                      <span className="credittab-assumed" title={cp.assumed_note ?? undefined}>
                        Supuesto
                      </span>
                    )}
                  </td>
                  <td className="num">{fmtMoney(cp.pv_mxn, 'MXN')}</td>
                  <td className="num">{fmtMoney(cp.cva_mxn, 'MXN')}</td>
                  <td className="num">{fmtRate(cp.hazard_rate)}</td>
                  <td className="num">{fmtRate(cp.recovery)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ProfileCard({ cp, pfeQuantile }: { cp: CreditCounterparty; pfeQuantile: number }) {
  return (
    <section className="radv-card" aria-labelledby="credittab-profile-title">
      <h2 id="credittab-profile-title">Perfil de {cp.counterparty}</h2>
      {cp.profile.length === 0 ? (
        <p className="radv-note">Sin swaps de tasa vivos: no hay perfil de exposición que simular.</p>
      ) : (
        <EChart option={profileOption(cp, pfeQuantile)} height={280} ariaLabel="Perfil de exposición" />
      )}
      {cp.excluded.length > 0 && (
        <div className="radv-note radv-note--warn" role="status">
          <strong>Operaciones excluidas de la exposición</strong>
          <ul className="credittab-list">
            {cp.excluded.map((x) => (
              <li key={x.id}>
                Operación #{x.id}: {x.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function NettingSetsCard({ cp }: { cp: CreditCounterparty }) {
  return (
    <section className="radv-card" aria-labelledby="credittab-ns-title">
      <h2 id="credittab-ns-title">Conjuntos de compensación</h2>
      {cp.netting_sets.length === 0 ? (
        <p className="radv-note">Sin conjuntos de compensación: la contraparte no tiene swaps de tasa vivos.</p>
      ) : (
        <ul className="credittab-list">
          {cp.netting_sets.map((ns) => (
            <li key={ns.curve}>
              <strong>
                {ns.curve} ({ns.currency})
              </strong>
              : {ns.trades.map((id) => `#${id}`).join(', ')} · PV {fmtMoney(ns.pv_mxn, 'MXN')} · CVA{' '}
              {fmtMoney(ns.cva_mxn, 'MXN')}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ParamsCard({
  cp,
  entry,
  paramsError,
  onSaved,
}: {
  cp: CreditCounterparty;
  entry: CreditParams | undefined;
  paramsError: string | null;
  onSaved: (saved: CreditParams) => void;
}) {
  const [inputs, setInputs] = useState<Inputs>({
    hazard: toPercentText(cp.hazard_rate),
    recovery: toPercentText(cp.recovery),
  });
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Otra contraparte, o valores vigentes distintos (tras guardar y recalcular): el formulario parte de lo vigente.
  useEffect(() => {
    setInputs({ hazard: toPercentText(cp.hazard_rate), recovery: toPercentText(cp.recovery) });
    setFieldErrors({});
    setFormError(null);
  }, [cp.counterparty, cp.hazard_rate, cp.recovery]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const errors: Partial<Record<Field, string>> = {};
    const values = {} as Record<keyof Inputs, number>;
    for (const key of Object.keys(FIELD_OF) as (keyof Inputs)[]) {
      const n = Number(inputs[key]);
      if (inputs[key].trim() === '' || !Number.isFinite(n)) errors[FIELD_OF[key]] = 'Ingresa un número válido';
      else values[key] = n;
    }
    setFormError(null);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setSaving(true);
    try {
      const saved = await setCreditParams({
        counterparty: cp.counterparty,
        hazard_rate: toDecimal(values.hazard),
        recovery: toDecimal(values.recovery),
      });
      onSaved(saved);
    } catch (err) {
      const apiError = toApiError(err);
      const field = (Object.values(FIELD_OF) as string[]).includes(apiError.field ?? '') ? (apiError.field as Field) : null;
      if (apiError.status === 400 && field) setFieldErrors({ [field]: apiError.message });
      else setFormError(apiError.message);
    } finally {
      setSaving(false);
    }
  };

  const fields: { key: keyof Inputs; id: string; label: string }[] = [
    { key: 'hazard', id: 'credittab-hazard', label: 'Prob. de incumplimiento anual (%)' },
    { key: 'recovery', id: 'credittab-recovery', label: 'Recuperación (%)' },
  ];
  const history = entry?.history ?? [];

  return (
    <section className="radv-card" aria-labelledby="credittab-params-title">
      <h2 id="credittab-params-title">Parámetros de crédito</h2>
      <form className="credittab-form" onSubmit={submit}>
        {fields.map(({ key, id, label }) => {
          const message = fieldErrors[FIELD_OF[key]];
          return (
            <div className="credittab-field" key={key}>
              <label htmlFor={id}>{label}</label>
              <input
                id={id}
                type="number"
                step="any"
                value={inputs[key]}
                aria-invalid={message ? true : undefined}
                aria-describedby={message ? `${id}-error` : undefined}
                onChange={(e) => setInputs((cur) => ({ ...cur, [key]: e.target.value }))}
              />
              {message && (
                <span className="credittab-field__error" id={`${id}-error`}>
                  {message}
                </span>
              )}
            </div>
          );
        })}
        <button type="submit" className="credittab-submit" disabled={saving}>
          Guardar parámetros
        </button>
      </form>
      {formError && (
        <p className="radv-note radv-note--error" role="alert">
          {formError}
        </p>
      )}
      {cp.assumed && cp.assumed_note && <p className="radv-note radv-note--warn">{cp.assumed_note}</p>}
      <h3 className="credittab-subtitle">Historial de parámetros</h3>
      {paramsError ? (
        <p className="radv-note radv-note--error" role="alert">
          {paramsError}
        </p>
      ) : history.length === 0 ? (
        <p className="credittab-empty">Sin parámetros capturados para esta contraparte.</p>
      ) : (
        <div className="radv-scroll">
          <table className="radv-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th className="num">Prob. de incumplimiento anual</th>
                <th className="num">Recuperación</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={`${h.created_at}-${i}`}>
                  <td>{fmtDate(h.as_of)}</td>
                  <td className="num">{fmtRate(h.hazard_rate)}</td>
                  <td className="num">{fmtRate(h.recovery)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function CreditTab() {
  const { snapshotId } = useSnapshot();
  const [state, setState] = useState<ExposureState>({ loading: true, data: null, error: null });
  const [selected, setSelected] = useState<string | null>(null);
  const [params, setParams] = useState<CreditParams[]>([]);
  const [paramsError, setParamsError] = useState<string | null>(null);
  // Guardar parámetros pide recalcular sin cambiar de snapshot.
  const [reloadTick, setReloadTick] = useState(0);
  const ticket = useRef(0);
  const lastSnapshot = useRef<string | null>(null);

  useEffect(() => {
    const mine = ++ticket.current;
    // Otro snapshot: lo anterior ya no aplica. Al recalcular sobre el mismo, se conserva atenuado.
    const sameSnapshot = lastSnapshot.current === snapshotId;
    lastSnapshot.current = snapshotId;
    setState((s) => ({ loading: true, data: sameSnapshot ? s.data : null, error: null }));
    creditExposure(snapshotId).then(
      (data) => {
        if (mine === ticket.current) setState({ loading: false, data, error: null });
      },
      (e) => {
        if (mine === ticket.current) setState({ loading: false, data: null, error: toApiError(e) });
      },
    );
    return () => {
      ticket.current++;
    };
  }, [snapshotId, reloadTick]);

  useEffect(() => {
    let live = true;
    listCreditParams().then(
      (list) => {
        if (live) setParams(list);
      },
      (e) => {
        if (live) setParamsError(toApiError(e).message);
      },
    );
    return () => {
      live = false;
    };
  }, []);

  const { data, error, loading } = state;
  // Por omisión, la primera; si la elegida ya no está (otro snapshot), también la primera.
  const cp = data ? (data.counterparties.find((c) => c.counterparty === selected) ?? data.counterparties[0]) : undefined;

  const saved = (entry: CreditParams) => {
    setParams((cur) =>
      cur.some((p) => p.counterparty === entry.counterparty)
        ? cur.map((p) => (p.counterparty === entry.counterparty ? entry : p))
        : [...cur, entry],
    );
    setReloadTick((t) => t + 1);
  };

  return (
    <div className="credittab">
      {loading && (
        <p className="radv-note" role="status">
          Simulando exposición…
        </p>
      )}
      {error && (
        <p className="radv-note radv-note--error" role="alert">
          {error.message}
        </p>
      )}
      {data && (
        <div className={`credittab-body${loading ? ' is-loading' : ''}`}>
          <p className="radv-note credittab-notice" role="note">
            {data.notice}
          </p>
          {data.warnings.length > 0 && (
            <div className="radv-note radv-note--warn" role="status">
              <ul className="credittab-list">
                {data.warnings.map((w, i) => (
                  <li key={i}>{w.message}</li>
                ))}
              </ul>
            </div>
          )}
          <CounterpartiesCard data={data} selected={cp?.counterparty ?? null} onSelect={setSelected} />
          {cp && (
            <>
              <ProfileCard cp={cp} pfeQuantile={data.pfe_quantile} />
              <div className="radv-grid2">
                <NettingSetsCard cp={cp} />
                <ParamsCard
                  cp={cp}
                  entry={params.find((p) => p.counterparty === cp.counterparty)}
                  paramsError={paramsError}
                  onSaved={saved}
                />
              </div>
            </>
          )}
          <p className="credittab-foot">
            {fmtNumber(data.n_paths, 0)} trayectorias Hull-White, semilla fija; solo swaps de tasa; sin colateral; los
            puntos mensuales no compensan entre monedas (el de hoy sí).
          </p>
        </div>
      )}
    </div>
  );
}
