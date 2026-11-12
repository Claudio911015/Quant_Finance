import type { EChartsCoreOption } from 'echarts/core';
import type { XvaCounterparty, XvaIncrementalResponse } from '../../api/xvaTypes';
import { EChart, cssColor } from '../../components/EChart';
import { fmtDate, fmtMoney, fmtNumber } from '../../lib/format';

type Series = { name: string; data: number[]; color: string; dashed?: boolean };

/** Opción común de las gráficas de perfil: fechas en el eje X, MXN en millones en el Y. */
function lineOption(dates: string[], series: Series[]): EChartsCoreOption {
  const axis = {
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    axisLabel: { color: cssColor('--text-dim') },
  };
  return {
    animation: false,
    grid: { left: 64, right: 16, top: 40, bottom: 40 },
    legend: { top: 0, right: 0, textStyle: { color: cssColor('--text-dim') } },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => fmtMoney(v, 'MXN'),
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
    },
    xAxis: { type: 'category', data: dates.map(fmtDate), ...axis },
    yAxis: {
      type: 'value',
      axisLabel: { color: cssColor('--text-dim'), formatter: (v: number) => `${fmtNumber(v / 1e6, 1)} M` },
      axisLine: axis.axisLine,
      splitLine: { lineStyle: { color: cssColor('--border') } },
    },
    series: series.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      symbolSize: 4,
      lineStyle: { color: s.color, width: 2, type: s.dashed ? 'dashed' : 'solid' },
      itemStyle: { color: s.color },
    })),
  };
}

/** Perfil de exposición sin descontar de una contraparte: EPE, ENE y PFE contra fecha, en MXN. */
export function profileOption(cp: XvaCounterparty, pfeQuantile?: number): EChartsCoreOption {
  const pfeName = pfeQuantile === undefined ? 'PFE' : `PFE ${parseFloat((pfeQuantile * 100).toFixed(4))} %`;
  return lineOption(
    cp.profile.map((p) => p.date),
    [
      { name: 'EPE', data: cp.profile.map((p) => p.epe_mxn), color: cssColor('--accent') },
      { name: 'ENE', data: cp.profile.map((p) => p.ene_mxn), color: cssColor('--pos') },
      { name: pfeName, data: cp.profile.map((p) => p.pfe_mxn), color: cssColor('--warn') },
    ],
  );
}

type IncrementalPoint = XvaIncrementalResponse['profile'][number];

export interface ExposurePoint {
  date: string;
  t: number;
  epe: number;
}

/** Un plazo del perfil alineado: EPE antes, EPE después y su diferencia (`null` donde un perfil no tiene valor). */
export interface AlignedExposure {
  date: string;
  t: number;
  before: number | null;
  after: number | null;
  increment: number | null;
}

/**
 * EPE de un perfil (ordenado por plazo) en `date`: su valor si tiene esa fecha; si no, interpolación lineal en el
 * plazo dentro de su rango; 0 pasado su último plazo (ya no hay exposición); `null` antes del primero.
 */
function epeAt(pts: ExposurePoint[], byDate: Map<string, ExposurePoint>, date: string, t: number): number | null {
  const own = byDate.get(date);
  if (own) return own.epe;
  const next = pts.findIndex((p) => p.t > t);
  if (next === -1) return pts.length === 0 ? null : 0;
  if (next === 0) return null;
  const lo = pts[next - 1];
  const hi = pts[next];
  return lo.epe + ((hi.epe - lo.epe) * (t - lo.t)) / (hi.t - lo.t);
}

/** Alinea dos perfiles de EPE por fecha (nunca por índice) y calcula el incremento: después menos antes. */
export function alignExposure(before: ExposurePoint[], after: ExposurePoint[]): AlignedExposure[] {
  const byT = (a: ExposurePoint, b: ExposurePoint) => a.t - b.t;
  const b = [...before].sort(byT);
  const a = [...after].sort(byT);
  const bDate = new Map(b.map((p) => [p.date, p]));
  const aDate = new Map(a.map((p) => [p.date, p]));
  const dates = new Map<string, number>();
  for (const p of [...b, ...a]) if (!dates.has(p.date)) dates.set(p.date, p.t);
  return [...dates]
    .map(([date, t]) => {
      const vb = epeAt(b, bDate, date, t);
      const va = epeAt(a, aDate, date, t);
      return { date, t, before: vb, after: va, increment: vb !== null && va !== null ? va - vb : null };
    })
    .sort((x, y) => x.t - y.t || x.date.localeCompare(y.date));
}

/** Plazos del perfil de la respuesta, con el incremento de exposición esperada de cada uno. */
function profileRows(profile: IncrementalPoint[]): AlignedExposure[] {
  return alignExposure(
    profile.map((p) => ({ date: p.date, t: p.t, epe: p.epe_before_mxn })),
    profile.map((p) => ({ date: p.date, t: p.t, epe: p.epe_after_mxn })),
  );
}

type WithIncrement = AlignedExposure & { increment: number };

/** Plazos de mayor y menor incremento (el primero si empatan); `null` si ninguno tiene incremento. */
export function incrementExtremes(rows: AlignedExposure[]): { max: WithIncrement; min: WithIncrement } | null {
  const valid = rows.filter((r): r is WithIncrement => r.increment !== null);
  if (valid.length === 0) return null;
  return {
    max: valid.reduce((best, r) => (r.increment > best.increment ? r : best)),
    min: valid.reduce((best, r) => (r.increment < best.increment ? r : best)),
  };
}

/** Línea bajo la gráfica: dónde el candidato más suma y más resta exposición. */
export function incrementSummary(rows: AlignedExposure[]): string | null {
  const ex = incrementExtremes(rows);
  if (!ex) return null;
  const at = (r: WithIncrement) => `${fmtMoney(r.increment, 'MXN')} a ${fmtNumber(r.t, 2)} años (${fmtDate(r.date)})`;
  return `Incremento de exposición: máximo ${at(ex.max)}; mínimo ${at(ex.min)}.`;
}

const NAME_BEFORE = 'Exposición esperada antes';
const NAME_AFTER = 'Exposición esperada después';
const NAME_INCREMENT = 'Incremento de exposición';

/** Rótulo de eje en MXN: millones si algún valor llega a un millón, el monto entero si no. */
function moneyAxisLabel(values: number[]): (v: number) => string {
  const millions = values.some((v) => Math.abs(v) >= 1e6);
  return (v) => (millions ? `${fmtNumber(v / 1e6, 1)} M` : fmtNumber(v, 0));
}

/**
 * EPE antes y después de la operación candidata (panel de arriba) y su incremento, que puede ser negativo cuando
 * la candidata compensa (panel de abajo, área alrededor de cero), con el plazo en años en el eje X de ambos.
 */
export function incrementalOption(profile: IncrementalPoint[]): EChartsCoreOption {
  const rows = profileRows(profile);
  const pairs = (pick: (r: AlignedExposure) => number | null) =>
    rows.flatMap((r) => {
      const v = pick(r);
      return v === null ? [] : [[r.t, v]];
    });
  const accent = cssColor('--accent');
  const warn = cssColor('--warn');
  const dim = cssColor('--text-dim');
  const tMax = rows.length > 0 && rows[rows.length - 1].t > 0 ? rows[rows.length - 1].t : 1;
  const epes = rows.flatMap((r) => [r.before ?? 0, r.after ?? 0]);
  const increments = rows.flatMap((r) => (r.increment === null ? [] : [r.increment]));
  const xAxis = (gridIndex: number, extra: object) => ({
    type: 'value',
    gridIndex,
    min: 0,
    max: tMax,
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    splitLine: { show: false },
    ...extra,
  });
  const yAxis = (gridIndex: number, values: number[]) => ({
    type: 'value',
    gridIndex,
    name: 'MXN',
    nameTextStyle: { color: dim },
    axisLabel: { color: dim, formatter: moneyAxisLabel(values) },
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    splitLine: { lineStyle: { color: cssColor('--border') } },
  });
  const line = (name: string, gridIndex: number, data: number[][], color: string, extra: object = {}) => ({
    name,
    type: 'line',
    xAxisIndex: gridIndex,
    yAxisIndex: gridIndex,
    data,
    symbolSize: 4,
    lineStyle: { color, width: 2 },
    itemStyle: { color },
    ...extra,
  });
  return {
    animation: false,
    grid: [
      { left: 72, right: 16, top: 48, height: 150 },
      { left: 72, right: 16, top: 240, height: 90 },
    ],
    legend: { top: 0, right: 0, data: [NAME_BEFORE, NAME_AFTER, NAME_INCREMENT], textStyle: { color: dim } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
      // Un solo cuadro con los tres valores del plazo, pase el cursor por el panel que pase.
      formatter: (params: { value?: number[] }[]) => {
        const row = rows.find((r) => r.t === params[0]?.value?.[0]);
        if (!row) return '';
        const show = (name: string, v: number | null) => `${name}: ${v === null ? '—' : fmtMoney(v, 'MXN')}`;
        return [
          `${fmtDate(row.date)} · ${fmtNumber(row.t, 2)} años`,
          show(NAME_BEFORE, row.before),
          show(NAME_AFTER, row.after),
          show(NAME_INCREMENT, row.increment),
        ].join('<br/>');
      },
    },
    xAxis: [
      xAxis(0, { axisLabel: { show: false }, axisTick: { show: false } }),
      xAxis(1, {
        name: 'Plazo (años)',
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: dim },
        axisLabel: { color: dim, formatter: (v: number) => fmtNumber(v, 1) },
      }),
    ],
    yAxis: [yAxis(0, epes), yAxis(1, increments)],
    series: [
      line(NAME_BEFORE, 0, pairs((r) => r.before), accent, { lineStyle: { color: accent, width: 2, type: 'dashed' } }),
      line(NAME_AFTER, 0, pairs((r) => r.after), accent),
      line(NAME_INCREMENT, 1, pairs((r) => r.increment), warn, { areaStyle: { color: warn, opacity: 0.25 } }),
      // Referencia de cero para leer cuándo la candidata resta exposición.
      {
        name: 'Cero',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: [[0, 0], [tMax, 0]],
        silent: true,
        symbol: 'none',
        tooltip: { show: false },
        lineStyle: { color: cssColor('--text-dim'), width: 1 },
      },
    ],
  };
}

export function XvaProfileChart({ cp, pfeQuantile }: { cp: XvaCounterparty; pfeQuantile: number }) {
  return <EChart option={profileOption(cp, pfeQuantile)} height={280} ariaLabel="Perfil de exposición" />;
}

export function IncrementalChart({ profile }: { profile: IncrementalPoint[] }) {
  const summary = incrementSummary(profileRows(profile));
  return (
    <div className="xva-inc__chart">
      <h3 className="xva-subtitle">Exposición esperada antes y después de la operación</h3>
      <EChart
        option={incrementalOption(profile)}
        height={392}
        ariaLabel="Exposición esperada antes y después de la operación, e incremento de exposición"
      />
      {summary && <p className="xva-note xva-note--plain">{summary}</p>}
    </div>
  );
}
