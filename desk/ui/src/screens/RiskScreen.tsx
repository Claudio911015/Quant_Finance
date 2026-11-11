import { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import {
  AllCommunityModule,
  ModuleRegistry,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
} from 'ag-grid-community';
import { ApiError, listTrades, riskDv01, riskScenarios, riskVar } from '../api/client';
import type { Dv01Response, ScenarioSpec, ScenariosResponse, Trade, TradeError, VarResponse } from '../api/types';
import { CSA_CURVE_NOTE } from '../lib/csaLabels';
import { productTitle } from './pricers/registry';
import { fmtMoney, fmtNumber, fmtRate } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import './RiskScreen.css';
// --- corte 6: pestañas de riesgo avanzado ---
import { RiskTabs } from './risk/RiskTabs';
// --- fin corte 6 ---

ModuleRegistry.registerModules([AllCommunityModule]);

/** Set fijo de escenarios; el orden es el de las columnas de la tabla. */
const SCENARIOS: ScenarioSpec[] = [
  { name: 'TIIE-F +50 pb', type: 'parallel', curve: 'TIIE-F', bp: 50 },
  { name: 'TIIE-F -50 pb', type: 'parallel', curve: 'TIIE-F', bp: -50 },
  { name: 'SOFR +50 pb', type: 'parallel', curve: 'SOFR', bp: 50 },
  { name: 'SOFR -50 pb', type: 'parallel', curve: 'SOFR', bp: -50 },
  { name: 'TIIE-F steepener 25 pb', type: 'steepener', curve: 'TIIE-F', bp: 25 },
  { name: 'SOFR steepener 25 pb', type: 'steepener', curve: 'SOFR', bp: 25 },
  { name: 'USDMXN +10 %', type: 'fx_spot', pct: 10 },
  { name: 'USDMXN -10 %', type: 'fx_spot', pct: -10 },
];

/* ---------- Carga de datos ---------- */

interface Load<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
}

function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, 'No se pudo conectar con el backend');
}

/**
 * Ejecuta `load` al montar y cada vez que cambia `deps`. Solo la última llamada escribe estado;
 * mientras recarga conserva el dato anterior (marcado `loading`) y, si falla, lo descarta.
 */
function useLoad<T>(load: () => Promise<T>, deps: unknown[]): Load<T> {
  const [state, setState] = useState<Load<T>>({ data: null, error: null, loading: true });
  const ticket = useRef(0);
  useEffect(() => {
    const mine = ++ticket.current;
    setState((s) => ({ ...s, loading: true }));
    load().then(
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

/* ---------- Utilidades ---------- */

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const signClass = (v: number | null | undefined) =>
  v == null || v === 0 ? '' : v > 0 ? 'risk-pos' : 'risk-neg';

function plainNumber(v: number): string {
  return Number.isInteger(v) ? fmtNumber(v, 0) : fmtNumber(v, 2);
}

function ExcludedNote({ errors }: { errors: TradeError[] }) {
  if (errors.length === 0) return null;
  return (
    <p className="risk-note risk-note--warn" role="status">
      Operaciones excluidas: {errors.map((e) => `#${e.id} (${e.error})`).join('; ')}
    </p>
  );
}

function ErrorLine({ error }: { error: ApiError | null }) {
  return error ? (
    <p className="risk-note risk-note--error" role="alert">
      {error.message}
    </p>
  ) : null;
}

/* ---------- Escalera de DV01 ---------- */

function ladderOption(data: Dv01Response | null): echarts.EChartsOption {
  if (!data) return {};
  const curves = Object.entries(data.curves);
  const days = [...new Set(curves.flatMap(([, c]) => c.points.map((p) => p.days)))].sort((a, b) => a - b);
  const labels = days.map((d) => {
    const names = new Set<string>();
    for (const [, c] of curves) for (const p of c.points) if (p.days === d) names.add(p.label);
    return [...names].join(' / ');
  });
  const dim = cssVar('--text-dim');
  const colors = [cssVar('--accent'), cssVar('--warn'), cssVar('--pos')]; // la tercera es MXN-USD (corte 3)
  const font = { color: dim, fontFamily: cssVar('--font-sans'), fontSize: 11 };
  return {
    animation: false,
    textStyle: font,
    color: colors,
    grid: { left: 64, right: 16, top: 28, bottom: 28 },
    legend: { top: 0, right: 0, textStyle: { color: cssVar('--text'), fontSize: 11 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (v) => (typeof v === 'number' ? fmtMoney(v, 'MXN') : String(v ?? '')),
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: cssVar('--border-strong') } },
      axisLabel: font,
    },
    yAxis: {
      type: 'value',
      axisLabel: { ...font, formatter: (v: number) => plainNumber(v) },
      splitLine: { lineStyle: { color: cssVar('--border') } },
    },
    series: curves.map(([name, c]) => ({
      name,
      type: 'bar',
      stack: 'dv01',
      barMaxWidth: 28,
      data: days.map((d) => c.points.find((p) => p.days === d)?.dv01_mxn ?? null),
    })),
  };
}

function LadderChart({ data }: { data: Dv01Response | null }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const c = echarts.init(el);
    chart.current = c;
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => c.resize()) : null;
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(ladderOption(data), true);
  }, [data]);

  return <div ref={host} className="risk-chart" role="img" aria-label="Escalera de DV01 por plazo" />;
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="risk-tile">
      <span className="risk-caption">{label}</span>
      <span className="risk-tile__value num">{fmtMoney(value, 'MXN')}</span>
    </div>
  );
}

// --- corte 3 --- la curva MXN-USD (solo viene si el snapshot trae puntos forward o base): pilares y su nota
const CSA_CURVE = 'MXN-USD';

function CsaCurveTable({ curve }: { curve: Dv01Response['curves'][string] }) {
  return (
    <div className="risk-csa">
      <h3 className="risk-caption">{CSA_CURVE} · DV01 por plazo</h3>
      <table className="risk-table" aria-label={`DV01 por plazo de ${CSA_CURVE}`}>
        <thead>
          <tr>
            <th>Plazo</th>
            <th className="num">Días</th>
            <th className="num">DV01</th>
          </tr>
        </thead>
        <tbody>
          {curve.points.map((p) => (
            <tr key={`${p.label}-${p.days}`}>
              <td>{p.label}</td>
              <td className="num">{fmtNumber(p.days, 0)}</td>
              <td className={`num ${signClass(p.dv01_mxn)}`}>{fmtNumber(p.dv01_mxn, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="risk-foot">{CSA_CURVE_NOTE}</p>
    </div>
  );
}
// --- fin corte 3 ---

function Dv01Section() {
  const { snapshotId } = useSnapshot();
  const { data, error, loading } = useLoad(() => riskDv01(snapshotId), [snapshotId]);

  return (
    <section className={`risk-card${loading ? ' is-loading' : ''}`} aria-labelledby="risk-dv01-title">
      <h2 id="risk-dv01-title">Escalera DV01</h2>
      <ErrorLine error={error} />
      {data && (
        <div className="risk-tiles">
          <Tile label="DV01 total" value={data.total_mxn} />
          <Tile label="Paralelo" value={data.parallel_mxn} />
          {Object.entries(data.curves).map(([name, c]) => (
            <Tile key={name} label={`${name} paralelo`} value={c.parallel_mxn} />
          ))}
        </div>
      )}
      <LadderChart data={data} />
      <p className="risk-foot">DV01 = PV base − PV con la curva +1 pb; positivo si el PV sube cuando bajan las tasas.</p>
      {data?.curves[CSA_CURVE] && <CsaCurveTable curve={data.curves[CSA_CURVE]} />}
      <ExcludedNote errors={data?.errors ?? []} />
    </section>
  );
}

/* ---------- Escenarios ---------- */

interface ScenarioRow {
  label: string;
  [key: string]: number | string | null;
}

const gridTheme = themeQuartz.withParams({
  backgroundColor: 'var(--bg-elev)',
  foregroundColor: 'var(--text)',
  borderColor: 'var(--border)',
  headerBackgroundColor: 'var(--bg)',
  headerTextColor: 'var(--text-dim)',
  rowHoverColor: 'var(--bg-hover)',
  fontFamily: 'var(--font-sans)',
  fontSize: 12,
  rowHeight: 26,
  spacing: 4,
  wrapperBorder: false,
  browserColorScheme: 'dark',
});

const columnDefs: ColDef<ScenarioRow>[] = [
  { field: 'label', headerName: 'Operación', width: 244, pinned: 'left', sortable: false, tooltipField: 'label' },
  ...SCENARIOS.map(
    (s, i): ColDef<ScenarioRow> => ({
      field: `s${i}`,
      headerName: s.name,
      flex: 1,
      minWidth: 90,
      sortable: false,
      wrapHeaderText: true,
      autoHeaderHeight: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: (p) => ['num', signClass(p.value as number | null)],
      valueFormatter: (p) => (p.value == null ? 'n/d' : fmtNumber(p.value as number, 0)),
      tooltipValueGetter: (p) => (p.data?.[`e${i}`] as string | null | undefined) ?? null,
    }),
  ),
];

function buildRows(res: ScenariosResponse, trades: Trade[]): { rows: ScenarioRow[]; total: ScenarioRow } {
  const byId = new Map(trades.map((t) => [t.id, t]));
  const ids: number[] = [];
  for (const sc of res.scenarios) for (const t of sc.trades) if (!ids.includes(t.id)) ids.push(t.id);
  const rows = ids.map((id): ScenarioRow => {
    const t = byId.get(id);
    const row: ScenarioRow = { label: t ? `#${id} ${productTitle(t.product)} · ${t.counterparty}` : `#${id}` };
    res.scenarios.forEach((sc, i) => {
      const cell = sc.trades.find((x) => x.id === id);
      row[`s${i}`] = cell?.pnl_mxn ?? null;
      row[`e${i}`] = cell?.error ?? null;
    });
    return row;
  });
  const total: ScenarioRow = { label: 'Total' };
  res.scenarios.forEach((sc, i) => {
    total[`s${i}`] = sc.total_mxn;
  });
  return { rows, total };
}

function ScenarioGrid({ rows, total }: { rows: ScenarioRow[]; total: ScenarioRow }) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<GridApi<ScenarioRow> | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    api.current = createGrid<ScenarioRow>(el, {
      theme: gridTheme,
      columnDefs,
      domLayout: 'autoHeight',
      suppressMovableColumns: true,
      suppressCellFocus: true,
      overlayNoRowsTemplate: 'Sin operaciones en el portafolio',
      getRowClass: (p) => (p.node.rowPinned ? 'risk-total' : undefined),
    });
    return () => {
      api.current?.destroy();
      api.current = null;
    };
  }, []);

  useEffect(() => {
    api.current?.setGridOption('rowData', rows);
    api.current?.setGridOption('pinnedBottomRowData', [total]);
  }, [rows, total]);

  return <div ref={host} className="risk-grid" />;
}

function ScenariosSection() {
  const { snapshotId } = useSnapshot();
  const { data, error, loading } = useLoad(async () => {
    const [res, trades] = await Promise.all([riskScenarios(snapshotId, SCENARIOS), listTrades()]);
    return buildRows(res, trades);
  }, [snapshotId]);

  const empty = useMemo(() => ({ rows: [] as ScenarioRow[], total: { label: 'Total' } as ScenarioRow }), []);
  const { rows, total } = data ?? empty;

  const hasFailedCells = data?.rows.some((r) => SCENARIOS.some((_, i) => typeof r[`e${i}`] === 'string')) ?? false;

  return (
    <section className={`risk-card${loading ? ' is-loading' : ''}`} aria-labelledby="risk-scn-title">
      <h2 id="risk-scn-title">Escenarios</h2>
      <p className="risk-foot">P&amp;L en MXN por operación frente al snapshot base.</p>
      <ErrorLine error={error} />
      <ScenarioGrid rows={rows} total={total} />
      {hasFailedCells && (
        <p className="risk-note risk-note--warn" role="status">
          Algunas celdas no se pudieron valuar (n/d): pasa el cursor para ver el motivo.
        </p>
      )}
    </section>
  );
}

/* ---------- VaR ---------- */

const UNIT_LABEL: Record<string, string> = { bp: 'pb', ret: 'rend.' };

function fmtVol(v: number, unit: string): string {
  return unit === 'ret' ? fmtRate(v) : `${fmtNumber(v, 2)} ${UNIT_LABEL[unit] ?? unit}`;
}

function parseField(text: string, field: string): number {
  const n = Number(text);
  if (text.trim() === '' || !Number.isFinite(n)) throw new ApiError(400, 'Ingresa un número válido', field);
  return n;
}

function VarSection() {
  const { snapshotId } = useSnapshot();
  const [horizon, setHorizon] = useState('10');
  const [confidence, setConfidence] = useState('99');
  const { data, error, loading } = useLoad<VarResponse>(async () => {
    const days = parseField(horizon, 'horizon_days');
    const pct = parseField(confidence, 'confidence');
    // El input va en %; la API recibe el decimal (sin ruido de punto flotante).
    return riskVar(snapshotId, days, Number((pct / 100).toPrecision(12)));
  }, [snapshotId, horizon, confidence]);

  const fieldError = (field: string) => (error?.field === field ? error.message : null);
  const generalError = error && error.field !== 'horizon_days' && error.field !== 'confidence' ? error : null;

  return (
    <section className={`risk-card risk-var${loading ? ' is-loading' : ''}`} aria-labelledby="risk-var-title">
      <h2 id="risk-var-title">Valor en riesgo (VaR)</h2>
      <div className="risk-var__inputs">
        <div className="risk-field">
          <label htmlFor="risk-horizon">Horizonte (días)</label>
          <input
            id="risk-horizon"
            type="number"
            step="any"
            value={horizon}
            aria-invalid={fieldError('horizon_days') ? true : undefined}
            onChange={(e) => setHorizon(e.target.value)}
          />
          {fieldError('horizon_days') && <span className="risk-field__error">{fieldError('horizon_days')}</span>}
        </div>
        <div className="risk-field">
          <label htmlFor="risk-confidence">Confianza (%)</label>
          <input
            id="risk-confidence"
            type="number"
            step="any"
            value={confidence}
            aria-invalid={fieldError('confidence') ? true : undefined}
            onChange={(e) => setConfidence(e.target.value)}
          />
          {fieldError('confidence') && <span className="risk-field__error">{fieldError('confidence')}</span>}
        </div>
      </div>
      <ErrorLine error={generalError} />
      {data && (
        <>
          <div className="risk-var__total">
            <span className="risk-caption">
              VaR {parseFloat((data.confidence * 100).toFixed(4))} % a {data.horizon_days}{' '}
              {data.horizon_days === 1 ? 'día' : 'días'}
            </span>
            <span className="risk-var__value num">{fmtMoney(data.var_mxn, 'MXN')}</span>
          </div>
          <table className="risk-table">
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
          <p className="risk-foot">
            Exposición y VaR en MXN. Exposición = P&amp;L ante +1 pb paralelo (tasas) o ante un rendimiento relativo
            unitario del spot (USDMXN).
          </p>
          <ExcludedNote errors={data.errors} />
        </>
      )}
    </section>
  );
}

export function RiskScreen() {
  return (
    <div className="risk">
      <h1>Riesgo</h1>
      {/* corte 6: lo de siempre pasa a la pestaña Sensibilidades */}
      <RiskTabs
        sensitivities={
          <>
            <div className="risk__top">
              <Dv01Section />
              <VarSection />
            </div>
            <ScenariosSection />
          </>
        }
      />
    </div>
  );
}
