import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDark,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
} from 'ag-grid-community';
import type { EChartsCoreOption } from 'echarts/core';
import { ApiError, refreshMarket, updateSnapshot } from '../api/client';
import type { CurvePoint, Quote, Snapshot, Source, SourceKey } from '../api/types';
import { EChart, cssColor } from '../components/EChart';
import { fmtNumber } from '../lib/format';
import { asOfText, kindText } from '../lib/provenance';
import { useSnapshot } from '../state/SnapshotContext';
import './MarketScreen.css';

ModuleRegistry.registerModules([AllCommunityModule]);

const CURVE_ORDER = ['TIIE-F', 'SOFR'];

const LIVE_ID = 'MKT-LIVE';
const READ_ONLY_NOTE = 'Mercado vivo se reconstruye en cada actualización; sus cotizaciones y el spot no se editan.';

const gridTheme = themeQuartz.withPart(colorSchemeDark).withParams({
  backgroundColor: 'var(--bg-elev)',
  foregroundColor: 'var(--text)',
  borderColor: 'var(--border)',
  headerBackgroundColor: 'var(--bg)',
  headerTextColor: 'var(--text-dim)',
  accentColor: 'var(--accent)',
  fontFamily: 'var(--font-sans)',
  fontSize: 12,
  rowHeight: 28,
  headerHeight: 28,
  wrapperBorderRadius: 4,
});

// Las cotizaciones viajan en decimal y se editan en %; el redondeo evita 6.750000000000001.
const decToPct = (dec: number) => Number((dec * 100).toFixed(6));
const pctToDec = (pct: number) => Number((pct / 100).toFixed(8));

function describeError(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

/* ---------- Gráficas ---------- */

function axisStyle() {
  return {
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    axisLabel: { color: cssColor('--text-dim') },
    nameTextStyle: { color: cssColor('--text-dim') },
    splitLine: { lineStyle: { color: cssColor('--border') } },
  };
}

function curveOption(points: CurvePoint[]): EChartsCoreOption {
  const pct = (v: number) => `${fmtNumber(v, 4)} %`;
  return {
    animation: false,
    grid: { left: 52, right: 16, top: 32, bottom: 36 },
    legend: { top: 0, right: 0, textStyle: { color: cssColor('--text-dim') } },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => pct(v),
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
    },
    xAxis: { type: 'value', name: 'días', nameLocation: 'middle', nameGap: 22, ...axisStyle() },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: cssColor('--text-dim'), formatter: (v: number) => `${fmtNumber(v, 2)} %` },
      axisLine: axisStyle().axisLine,
      splitLine: axisStyle().splitLine,
    },
    series: [
      {
        name: 'Cero',
        type: 'line',
        data: points.map((p) => [p.days, p.zero * 100]),
        symbolSize: 5,
        lineStyle: { color: cssColor('--accent'), width: 2 },
        itemStyle: { color: cssColor('--accent') },
      },
      {
        // El forward de cada punto rige entre el pilar anterior y ese pilar.
        name: 'Forward',
        type: 'line',
        step: 'start',
        data: points.map((p) => [p.days, p.forward * 100]),
        symbolSize: 5,
        lineStyle: { color: cssColor('--warn'), width: 2 },
        itemStyle: { color: cssColor('--warn') },
      },
    ],
  };
}

function surfaceOption(surface: Snapshot['vol_surface']): EChartsCoreOption {
  const cells: [number, number, number][] = [];
  surface.vols.forEach((row, i) => row.forEach((v, j) => cells.push([j, i, v * 100])));
  const values = cells.map((c) => c[2]);
  return {
    animation: false,
    grid: { left: 56, right: 16, top: 8, bottom: 84 },
    tooltip: {
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
      formatter: (p: { value: [number, number, number] }) =>
        `${surface.expiry_days[p.value[1]]} d · K ${fmtNumber(surface.strikes[p.value[0]], 2)}<br/>vol ${fmtNumber(p.value[2], 2)} %`,
    },
    xAxis: {
      type: 'category',
      name: 'strike',
      nameLocation: 'middle',
      nameGap: 22,
      data: surface.strikes.map((k) => fmtNumber(k, 2)),
      splitArea: { show: false },
      axisLine: axisStyle().axisLine,
      axisLabel: axisStyle().axisLabel,
      nameTextStyle: axisStyle().nameTextStyle,
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: surface.expiry_days.map((d) => `${d} d`),
      axisLine: axisStyle().axisLine,
      axisLabel: axisStyle().axisLabel,
    },
    visualMap: {
      min: Math.min(...values),
      max: Math.max(...values),
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 12,
      itemHeight: 140,
      text: ['vol %', ''],
      textStyle: { color: cssColor('--text-dim') },
      inRange: { color: [cssColor('--bg-hover'), cssColor('--accent')] },
    },
    series: [
      {
        type: 'heatmap',
        data: cells,
        label: {
          show: true,
          color: cssColor('--text'),
          formatter: (p: { value: [number, number, number] }) => fmtNumber(p.value[2], 2),
        },
        itemStyle: { borderColor: cssColor('--bg-elev'), borderWidth: 1 },
      },
    ],
  };
}

/* ---------- Procedencia ---------- */

function SourceTag({ source }: { source: Source }) {
  return (
    <p className="market__source">
      <span className={`market__kind market__kind--${source.kind}`}>{kindText(source.kind)}</span>
      <span className="market__source-label">{source.label}</span>
      <span className="market__source-date">{asOfText(source.as_of)}</span>
    </p>
  );
}

/* ---------- Tabla de cotizaciones (AG Grid) ---------- */

interface QuoteRow {
  id: string;
  label: string;
  type: string;
  days: number;
  ratePct: number;
}

/** Devuelve `true` si el backend aceptó la tasa; `false` revierte la celda. */
type CommitQuote = (quoteId: string, ratePct: number | null) => Promise<boolean>;

const REVERT = 'revert';

function QuotesGrid({
  quotes,
  readOnly,
  onCommit,
}: {
  quotes: Quote[];
  readOnly: boolean;
  onCommit: CommitQuote;
}) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<GridApi<QuoteRow> | null>(null);
  const commit = useRef(onCommit);
  // La rejilla se crea una sola vez; `editable` consulta esta referencia en cada intento de edición.
  const locked = useRef(readOnly);
  const rows = useMemo<QuoteRow[]>(
    () =>
      quotes.map((q) => ({
        id: q.id,
        label: q.label,
        type: q.type,
        days: q.days,
        ratePct: decToPct(q.rate),
      })),
    [quotes],
  );

  useEffect(() => {
    commit.current = onCommit;
  }, [onCommit]);

  useEffect(() => {
    locked.current = readOnly;
  }, [readOnly]);

  useEffect(() => {
    if (!host.current) return;
    const columnDefs: ColDef<QuoteRow>[] = [
      { field: 'label', headerName: 'Plazo' },
      { field: 'type', headerName: 'Tipo' },
      { field: 'days', headerName: 'Días', type: 'rightAligned', cellClass: 'num' },
      {
        field: 'ratePct',
        headerName: 'Tasa (%)',
        type: 'rightAligned',
        cellClass: 'num',
        editable: () => !locked.current,
        cellEditor: 'agNumberCellEditor',
        valueFormatter: (p) => (p.value == null ? '' : fmtNumber(p.value, 4)),
      },
    ];
    const grid = createGrid<QuoteRow>(host.current, {
      theme: gridTheme,
      columnDefs,
      defaultColDef: { flex: 1, sortable: false, resizable: false, suppressMovable: true },
      getRowId: (p) => p.data.id,
      domLayout: 'autoHeight',
      suppressColumnVirtualisation: true, // solo 4 columnas; también deja la tabla completa en jsdom
      singleClickEdit: true,
      stopEditingWhenCellsLoseFocus: true,
      onCellValueChanged: async (e) => {
        if (e.source === REVERT || e.newValue === e.oldValue) return;
        const ok = await commit.current(e.data.id, e.newValue ?? null);
        if (!ok) e.node.setDataValue('ratePct', e.oldValue, REVERT);
      },
    });
    api.current = grid;
    return () => {
      grid.destroy();
      api.current = null;
    };
  }, []);

  useEffect(() => {
    api.current?.setGridOption('rowData', rows);
  }, [rows]);

  return <div ref={host} className="market__grid" aria-label="Cotizaciones" />;
}

/* ---------- Pantalla ---------- */

function CurvePanel({
  name,
  snapshot,
  error,
  onCommit,
}: {
  name: string;
  snapshot: Snapshot;
  error: string | null;
  onCommit: CommitQuote;
}) {
  const source = snapshot.sources[`curve:${name}` as SourceKey];
  const curve = snapshot.curves[name];
  const quotes = useMemo(() => snapshot.quotes.filter((q) => q.curve === name), [snapshot, name]);
  const option = useMemo(() => curveOption(curve.points), [curve]);
  return (
    <section className="market__panel" aria-labelledby={`curve-${name}`}>
      <header className="market__panel-head">
        <h2 id={`curve-${name}`}>{name}</h2>
        <span className="market__meta">
          {curve.currency} · cupón {curve.period_days} d
        </span>
        {source && <SourceTag source={source} />}
      </header>
      <div className="market__split">
        <EChart option={option} ariaLabel={`Curva ${name}: cero y forward`} />
        <div className="market__table">
          <QuotesGrid quotes={quotes} readOnly={snapshot.read_only} onCommit={onCommit} />
          {error && (
            <p role="alert" className="market__error">
              {error}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function SpotField({ snapshot, onSave }: { snapshot: Snapshot; onSave: (n: number) => Promise<string | null> }) {
  const current = String(snapshot.fx.spot);
  const [draft, setDraft] = useState(current);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(current);
  }, [current]);

  async function save() {
    if (draft === current) return;
    const n = Number(draft);
    if (draft.trim() === '' || !Number.isFinite(n)) {
      setError('El spot debe ser un número');
      setDraft(current);
      return;
    }
    const message = await onSave(n);
    setError(message);
    if (message) setDraft(current);
  }

  return (
    <div className="market__spot">
      <label className="market__field">
        <span>Spot {snapshot.fx.pair}</span>
        <input
          className="market__input num"
          type="number"
          step="any"
          disabled={snapshot.read_only}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => void save()}
          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        />
      </label>
      <SourceTag source={snapshot.sources.spot} />
      {error && (
        <p role="alert" className="market__error">
          {error}
        </p>
      )}
    </div>
  );
}

export function MarketScreen() {
  const { snapshot, snapshots, setSnapshot, setSnapshotId, reload, error } = useSnapshot();
  const [quoteError, setQuoteError] = useState<{ curve: string; message: string } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const snapshotKey = snapshot?.id;

  useEffect(() => {
    setQuoteError(null);
  }, [snapshotKey]);

  const surface = useMemo(() => (snapshot ? surfaceOption(snapshot.vol_surface) : null), [snapshot]);

  async function refresh() {
    // Se anota antes de pedir: si MKT-LIVE no existía, el refresco lo crea y la pantalla cambia a él.
    const hadLive = snapshots.some((s) => s.id === LIVE_ID);
    setRefreshing(true);
    setRefreshStatus(null);
    try {
      const r = await refreshMarket();
      let text = `Datos al ${r.treasury_latest} · SOFR ${r.sofr_latest} · FRED ${r.fred_latest}`;
      if (!hadLive) {
        setSnapshotId(LIVE_ID);
        text += ' · Se cambió a Mercado vivo (SOFR aproximada)';
      }
      setRefreshStatus({ ok: true, text });
      await reload();
    } catch (e) {
      setRefreshStatus({ ok: false, text: describeError(e) });
    } finally {
      setRefreshing(false);
    }
  }

  // Botón y resultado van juntos: el mensaje (fechas o error del backend) queda bajo el botón.
  const refreshControl = (
    <div className="market__refresh-box">
      <button type="button" className="market__btn" disabled={refreshing} onClick={() => void refresh()}>
        {refreshing ? 'Actualizando…' : 'Actualizar datos'}
      </button>
      {refreshStatus && (
        <p
          role={refreshStatus.ok ? 'status' : 'alert'}
          className={refreshStatus.ok ? 'market__refresh' : 'market__error'}
        >
          {refreshStatus.text}
        </p>
      )}
    </div>
  );

  if (!snapshot || !surface) {
    return (
      <div className="market">
        <header className="market__head">
          <h1>Mercado</h1>
          {refreshControl}
        </header>
        <p className="market__meta">{error ? 'Sin datos de mercado' : 'Cargando snapshot…'}</p>
      </div>
    );
  }

  const curveNames = [
    ...CURVE_ORDER.filter((n) => n in snapshot.curves),
    ...Object.keys(snapshot.curves).filter((n) => !CURVE_ORDER.includes(n)),
  ];

  const commitQuote = (curve: string): CommitQuote => async (quoteId, ratePct) => {
    setQuoteError(null);
    if (ratePct == null) {
      setQuoteError({ curve, message: 'La tasa debe ser un número' });
      return false;
    }
    try {
      setSnapshot(await updateSnapshot(snapshot.id, { quotes: [{ id: quoteId, rate: pctToDec(ratePct) }] }));
      return true;
    } catch (e) {
      setQuoteError({ curve, message: describeError(e) });
      return false;
    }
  };

  const saveSpot = async (spot: number): Promise<string | null> => {
    try {
      setSnapshot(await updateSnapshot(snapshot.id, { spot }));
      return null;
    } catch (e) {
      return describeError(e);
    }
  };

  return (
    <div className="market">
      <header className="market__head">
        <h1>Mercado</h1>
        <div className="market__actions">
          <SpotField snapshot={snapshot} onSave={saveSpot} />
          {refreshControl}
        </div>
      </header>
      {snapshot.read_only && (
        <p role="note" className="market__note">
          {READ_ONLY_NOTE}
        </p>
      )}

      {curveNames.map((name) => (
        <CurvePanel
          key={name}
          name={name}
          snapshot={snapshot}
          error={quoteError?.curve === name ? quoteError.message : null}
          onCommit={commitQuote(name)}
        />
      ))}

      <div className="market__split">
        <section className="market__panel" aria-labelledby="surface-title">
          <header className="market__panel-head">
            <h2 id="surface-title">Superficie de volatilidad {snapshot.vol_surface.pair}</h2>
            <span className="market__meta">plazo × strike, vol en %</span>
            <SourceTag source={snapshot.sources.surface} />
          </header>
          <EChart option={surface} height={300} ariaLabel="Mapa de calor de la superficie de volatilidad" />
        </section>

        <section className="market__panel" aria-labelledby="hw-title">
          <header className="market__panel-head">
            <h2 id="hw-title">Parámetros Hull-White</h2>
            <span className="market__meta">solo lectura</span>
          </header>
          <table className="market__hw" aria-label="Parámetros Hull-White">
            <thead>
              <tr>
                <th scope="col">Curva</th>
                <th scope="col" className="num">
                  a
                </th>
                <th scope="col" className="num">
                  σ
                </th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(snapshot.hw).map(([name, p]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td className="num">{fmtNumber(p.a, 4)}</td>
                  <td className="num">{fmtNumber(p.sigma, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
