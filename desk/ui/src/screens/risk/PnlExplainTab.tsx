import { Fragment, useEffect, useState } from 'react';
import { BarChart } from 'echarts/charts';
import { MarkLineComponent } from 'echarts/components';
import { use, type EChartsCoreOption } from 'echarts/core';
import { ApiError } from '../../api/client';
import { pnlExplain } from '../../api/riskClient';
import type { ExplainResponse } from '../../api/riskTypes';
import type { SnapshotSummary } from '../../api/types';
import { EChart, cssColor } from '../../components/EChart';
import { fmtDate, fmtMoney, fmtNumber } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import { productTitle } from '../pricers/registry';
import './PnlExplainTab.css';

// `EChart` solo registra líneas y mapas de calor; la cascada necesita barras (y la línea del cero).
use([BarChart, MarkLineComponent]);

const WATERFALL_LABEL = 'Cascada del P&L explicado';
const TOTAL_LABEL = 'P&L total';

/* ---------- Gráfica de cascada ---------- */

interface Bar {
  label: string;
  value: number;
  /** Acumulado antes de esta barra (0 en la barra del total). */
  start: number;
}

/** Eje en MXN compacto: la cascada mezcla pesos con millones. */
function axisMoney(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e6) return `${fmtNumber(v / 1e6, 1)} M`;
  if (a >= 1e3) return `${fmtNumber(v / 1e3, 0)} k`;
  return fmtNumber(v, 0);
}

/**
 * Opción de ECharts para la cascada: una barra flotante por paso, en el orden de `steps`, y una
 * última barra con el P&L total. Cada barra es el tramo [min, max] entre el acumulado anterior y
 * el posterior; se arma apilando una base transparente más un tramo sobre el cero y otro bajo el
 * cero (una barra que cruza el cero usa los dos). Función pura: no toca ECharts.
 */
export function cascadeOption(res: ExplainResponse): EChartsCoreOption {
  const pos = cssColor('--pos');
  const neg = cssColor('--neg');
  const axis = {
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    axisLabel: { color: cssColor('--text-dim') },
    splitLine: { lineStyle: { color: cssColor('--border') } },
  };

  let running = 0;
  const bars: Bar[] = res.steps.map((s) => {
    const value = res.totals.components[s.key] ?? 0;
    const start = running;
    running += value;
    return { label: s.label, value, start };
  });
  bars.push({ label: TOTAL_LABEL, value: res.totals.pnl, start: 0 });

  const base: number[] = [];
  const up: number[] = [];
  const down: number[] = [];
  for (const b of bars) {
    const end = b.start + b.value;
    const lo = Math.min(b.start, end);
    const hi = Math.max(b.start, end);
    if (lo >= 0) {
      base.push(lo);
      up.push(hi - lo);
      down.push(0);
    } else if (hi <= 0) {
      base.push(hi);
      up.push(0);
      down.push(lo - hi);
    } else {
      // Cruza el cero: sin base, un tramo hacia cada lado.
      base.push(0);
      up.push(hi);
      down.push(lo);
    }
  }
  const colored = (values: number[]) =>
    values.map((v, i) => ({ value: v, itemStyle: { color: bars[i].value >= 0 ? pos : neg } }));

  return {
    animation: false,
    grid: { left: 64, right: 16, top: 16, bottom: 72 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
      formatter: (params: { dataIndex: number }[]) => {
        const b = bars[params[0].dataIndex];
        return `${b.label}<br/>${fmtMoney(b.value, 'MXN')}`;
      },
    },
    xAxis: {
      type: 'category',
      data: bars.map((b) => b.label),
      ...axis,
      // Con `onZero` las etiquetas quedarían encima de las barras negativas.
      axisLine: { onZero: false, lineStyle: axis.axisLine.lineStyle },
      axisLabel: { color: cssColor('--text-dim'), interval: 0, width: 84, overflow: 'break' },
    },
    yAxis: { type: 'value', ...axis, axisLabel: { color: cssColor('--text-dim'), formatter: axisMoney } },
    series: [
      {
        name: 'Base',
        type: 'bar',
        stack: 'cascada',
        silent: true,
        itemStyle: { color: 'transparent' },
        emphasis: { disabled: true },
        data: base,
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: cssColor('--border-strong'), type: 'solid' },
          data: [{ yAxis: 0 }],
        },
      },
      { name: 'Tramo sobre el cero', type: 'bar', stack: 'cascada', barMaxWidth: 56, data: colored(up) },
      { name: 'Tramo bajo el cero', type: 'bar', stack: 'cascada', barMaxWidth: 56, data: colored(down) },
    ],
  };
}

/* ---------- Selección de snapshots ---------- */

interface Pick {
  from?: string;
  to?: string;
}

/** `?from=&to=` de la URL inicial (RiskTabs conserva el resto de la consulta). */
function initialPick(): Pick {
  const q = new URLSearchParams(window.location.search);
  return { from: q.get('from') ?? undefined, to: q.get('to') ?? undefined };
}

/**
 * Rango por omisión: `Hasta` = snapshot activo y `Desde` = el de mayor `as_of` anterior; si no hay
 * anterior, `Desde` = el activo y `Hasta` = el posterior más cercano. `null` si no hay dos snapshots.
 */
function defaultRange(snapshots: SnapshotSummary[], currentId: string): { from: string; to: string } | null {
  const current = snapshots.find((s) => s.id === currentId);
  if (!current || snapshots.length < 2) return null;
  const others = snapshots.filter((s) => s.id !== current.id);
  const byDate = (a: SnapshotSummary, b: SnapshotSummary) => a.as_of.localeCompare(b.as_of) || a.id.localeCompare(b.id);
  const before = others.filter((s) => s.as_of < current.as_of).sort(byDate).pop();
  if (before) return { from: before.id, to: current.id };
  const after = others.filter((s) => s.as_of > current.as_of).sort(byDate)[0];
  if (after) return { from: current.id, to: after.id };
  // Hueco del plan: todos con el mismo as_of (no hay anterior ni posterior). Lo más conservador es
  // comparar el activo contra el primero que no lo sea; el backend acepta fechas iguales.
  return { from: others.sort(byDate)[0].id, to: current.id };
}

interface Failure {
  field: string | null;
  message: string;
}

/* ---------- Pestaña ---------- */

export function PnlExplainTab() {
  const { snapshotId, snapshots } = useSnapshot();
  // Lo que el usuario (o la URL) eligió; lo que falte o ya no exista sigue al snapshot activo.
  const [pick, setPick] = useState<Pick>(initialPick);
  const [data, setData] = useState<ExplainResponse | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [loading, setLoading] = useState(false);

  const range = defaultRange(snapshots, snapshotId);
  const choose = (picked: string | undefined, fallback: string | undefined) =>
    picked && snapshots.some((s) => s.id === picked) ? picked : (fallback ?? '');
  const from = choose(pick.from, range?.from);
  const to = choose(pick.to, range?.to);

  useEffect(() => {
    if (!from || !to) {
      setData(null);
      setFailure(null);
      setLoading(false);
      return;
    }
    // Solo la última petición escribe estado.
    let stale = false;
    setLoading(true);
    setFailure(null);
    pnlExplain(from, to).then(
      (r) => {
        if (stale) return;
        setData(r);
        setLoading(false);
      },
      (e: unknown) => {
        if (stale) return;
        setData(null);
        setFailure(
          e instanceof ApiError
            ? { field: e.field, message: e.message }
            : { field: null, message: 'No se pudo conectar con el backend' },
        );
        setLoading(false);
      },
    );
    return () => {
      stale = true;
    };
  }, [from, to]);

  const options = snapshots.map((s) => (
    <option key={s.id} value={s.id}>
      {`${s.id} · ${fmtDate(s.as_of)}`}
    </option>
  ));
  const fieldError = (field: 'from' | 'to') => (failure?.field === field ? failure.message : null);
  const generalError = failure && failure.field !== 'from' && failure.field !== 'to' ? failure.message : null;
  const needTwo = snapshots.length < 2;

  return (
    <div className="pnlx">
      <section className="radv-card" aria-label="Rango del P&L explicado">
        <h2>P&amp;L explicado</h2>
        <div className="pnlx-controls">
          <div className="pnlx-field">
            <label className="pnlx-label">
              Desde
              <select
                className="pnlx-select"
                value={from}
                aria-invalid={fieldError('from') ? true : undefined}
                onChange={(e) => setPick({ from: e.target.value, to })}
              >
                {from === '' && <option value="">Elige un snapshot</option>}
                {options}
              </select>
            </label>
            {fieldError('from') && (
              <p className="pnlx-field-error" role="alert">
                {fieldError('from')}
              </p>
            )}
          </div>
          <div className="pnlx-field">
            <label className="pnlx-label">
              Hasta
              <select
                className="pnlx-select"
                value={to}
                aria-invalid={fieldError('to') ? true : undefined}
                onChange={(e) => setPick({ from, to: e.target.value })}
              >
                {to === '' && <option value="">Elige un snapshot</option>}
                {options}
              </select>
            </label>
            {fieldError('to') && (
              <p className="pnlx-field-error" role="alert">
                {fieldError('to')}
              </p>
            )}
          </div>
          {data && (
            <span className="pnlx-meta">
              {fmtDate(data.from.as_of)} → {fmtDate(data.to.as_of)} · MXN
            </span>
          )}
        </div>
        {needTwo && (
          <p className="radv-note radv-note--warn" role="status">
            Se necesitan dos snapshots
          </p>
        )}
        {loading && (
          <p className="radv-note" role="status">
            Calculando…
          </p>
        )}
        {generalError && (
          <p className="radv-note radv-note--error" role="alert">
            {generalError}
          </p>
        )}
      </section>

      {data && (
        <>
          <section className={`radv-card${loading ? ' is-loading' : ''}`} aria-label="Cascada">
            <h2>Cascada</h2>
            <EChart option={cascadeOption(data)} height={340} ariaLabel={WATERFALL_LABEL} />
          </section>

          <section className={`radv-card${loading ? ' is-loading' : ''}`} aria-label="Detalle por operación">
            <h2>Detalle por operación</h2>
            <div className="radv-scroll">
              <table className="radv-table pnlx-table">
                <thead>
                  <tr>
                    <th className="num">ID</th>
                    <th>Producto</th>
                    <th>Contraparte</th>
                    <th className="num">P&amp;L</th>
                    {data.steps.map((s) => (
                      <th key={s.key} className="num">
                        {s.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <Fragment key={r.id}>
                      <tr>
                        <td className="num">{r.id}</td>
                        <td>{productTitle(r.product)}</td>
                        <td>{r.counterparty}</td>
                        {r.error !== null || r.pnl === null || r.components === null ? (
                          <>
                            <td className="num">—</td>
                            <td className="pnlx-error" colSpan={data.steps.length}>
                              {r.error}
                            </td>
                          </>
                        ) : (
                          <>
                            <Money value={r.pnl} />
                            {data.steps.map((s) => (
                              <Money key={s.key} value={r.components![s.key]} />
                            ))}
                          </>
                        )}
                      </tr>
                      {r.explain_error && (
                        <tr className="pnlx-note-row">
                          <td colSpan={4 + data.steps.length}>
                            <p className="radv-note radv-note--warn" role="status">
                              {`No se pudo abrir la cascada de la operación ${r.id}; todo su P&L va al residuo: ${r.explain_error}`}
                            </p>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="pnlx-total">
                    <th scope="row" colSpan={3}>
                      Total
                    </th>
                    <Money value={data.totals.pnl} />
                    {data.steps.map((s) => (
                      <Money key={s.key} value={data.totals.components[s.key]} />
                    ))}
                  </tr>
                </tfoot>
              </table>
            </div>
            <p className="pnlx-foot">
              La suma de los pasos más el residuo es el P&amp;L de la pestaña P&amp;L; el orden de la cascada importa
              (ver Metodología).
            </p>
          </section>
        </>
      )}
    </div>
  );
}

/** Celda de importe en MXN; los negativos se pintan. */
function Money({ value }: { value: number }) {
  return <td className={`num${value < 0 ? ' pnlx-neg' : ''}`}>{fmtMoney(value, 'MXN')}</td>;
}
