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
import { ApiError, pnl } from '../api/client';
import type { PnlResponse, PnlRow, SnapshotSummary, TradeStatus } from '../api/types';
import { fmtDate, fmtNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import { productTitle } from './pricers/registry';
import './PnlPanel.css';

ModuleRegistry.registerModules([AllCommunityModule]);

/** Fila de la tabla: una operación o la fila fija de total. */
type GridRow = Partial<Omit<PnlRow, 'product'>> & { product?: string; total?: boolean };

const STATUS_LABEL: Record<TradeStatus, string> = {
  no_pactada: 'No pactada',
  viva: 'Viva',
  vencida: 'Vencida',
  terminada: 'Terminada',
  ejercida: 'Ejercida',
};

const theme = themeQuartz.withPart(colorSchemeDark).withParams({
  browserColorScheme: 'dark',
  backgroundColor: 'var(--bg)',
  foregroundColor: 'var(--text)',
  borderColor: 'var(--border)',
  headerBackgroundColor: 'var(--bg-elev)',
  headerTextColor: 'var(--text-dim)',
  rowHoverColor: 'var(--bg-hover)',
  accentColor: 'var(--accent)',
  fontFamily: 'var(--font-sans)',
  fontSize: 12,
  headerFontSize: 11,
  headerFontWeight: 500,
  rowHeight: 26,
  headerHeight: 28,
  spacing: 6,
  wrapperBorderRadius: 4,
});

const numberCell = { type: 'rightAligned', cellClass: 'num' } as const;

const statusFormatter = (p: { value?: TradeStatus | null }) => (p.value ? STATUS_LABEL[p.value] : '');

/** Una columna de cifras en MXN; los negativos se pintan; la fila con error no trae cifras. */
function moneyCol(colId: keyof PnlRow, headerName: string, showError = false): ColDef<GridRow> {
  return {
    colId,
    field: colId,
    headerName,
    width: 112,
    valueFormatter: (p) =>
      showError && p.data?.error ? 'Error' : p.value == null ? '' : fmtNumber(p.value, 2),
    cellClassRules: {
      pnl__neg: (p) => typeof p.value === 'number' && p.value < 0,
      'pnl__cell-error': (p) => showError && !!p.data?.error,
    },
    ...numberCell,
  };
}

/** Exportadas para la prueba de anchos: la suma de los anchos mínimos debe caber en 1280 px. */
export const columnDefs: ColDef<GridRow>[] = [
  { colId: 'id', field: 'id', headerName: 'ID', width: 56, ...numberCell },
  {
    colId: 'product',
    field: 'product',
    headerName: 'Producto',
    width: 132,
    valueFormatter: (p) => (p.value == null ? '' : productTitle(p.value)),
  },
  { colId: 'counterparty', field: 'counterparty', headerName: 'Contraparte', flex: 1, minWidth: 130 },
  { colId: 'status_from', field: 'status_from', headerName: 'Estado desde', width: 100, valueFormatter: statusFormatter },
  { colId: 'status_to', field: 'status_to', headerName: 'Estado hasta', width: 100, valueFormatter: statusFormatter },
  moneyCol('pv_from', 'PV desde'),
  moneyCol('pv_to', 'PV hasta'),
  moneyCol('settled', 'Liquidado'),
  moneyCol('pnl', 'P&L', true),
];

/** Texto del tooltip de una fila: el error, o los avisos del backend. */
function rowTip(row: GridRow | undefined): string | undefined {
  if (!row) return undefined;
  if (row.error) return row.error;
  const msgs = (row.warnings ?? []).map((w) => w.message);
  return msgs.length > 0 ? msgs.join('\n') : undefined;
}

/** Snapshot de `as_of` anterior más cercano al de `toId`; '' si no hay ninguno. */
function defaultFrom(snapshots: SnapshotSummary[], toId: string): string {
  const to = snapshots.find((s) => s.id === toId);
  if (!to) return '';
  let best: SnapshotSummary | null = null;
  for (const s of snapshots) {
    if (s.as_of < to.as_of && (best === null || s.as_of > best.as_of)) best = s;
  }
  return best?.id ?? '';
}

const optionLabel = (s: SnapshotSummary) => `${s.label} · ${fmtDate(s.as_of)}`;

interface Errors {
  from: string | null;
  to: string | null;
  general: string | null;
}

const NO_ERRORS: Errors = { from: null, to: null, general: null };

export default function PnlPanel() {
  const { snapshotId, snapshots } = useSnapshot();
  // Lo que el usuario eligió; mientras no elija, "Hasta" sigue al snapshot activo y
  // "Desde" al de `as_of` anterior más cercano.
  const [toPick, setToPick] = useState<string | null>(null);
  const [fromPick, setFromPick] = useState<string | null>(null);
  const [data, setData] = useState<PnlResponse | null>(null);
  const [errors, setErrors] = useState<Errors>(NO_ERRORS);
  const [loading, setLoading] = useState(false);
  const gridEl = useRef<HTMLDivElement>(null);
  const gridApi = useRef<GridApi<GridRow> | null>(null);
  // Solo el último cálculo escribe estado.
  const latest = useRef(0);

  const known = (id: string) => snapshots.some((s) => s.id === id);
  const toId = known(toPick ?? snapshotId) ? (toPick ?? snapshotId) : '';
  const fromId = fromPick !== null && known(fromPick) ? fromPick : defaultFrom(snapshots, toId);

  useEffect(() => {
    const api = createGrid<GridRow>(gridEl.current!, {
      theme,
      columnDefs,
      localeText: { noRowsToShow: 'Sin resultados: elige las fechas y presiona Calcular.' },
      defaultColDef: {
        sortable: true,
        tooltipValueGetter: (p) => rowTip(p.data),
      },
      rowData: [],
      pinnedBottomRowData: [],
      getRowId: (p) => (p.data.total ? 'total' : String(p.data.id)),
      getRowClass: (p) =>
        p.data?.total
          ? 'row-total'
          : p.data?.error
            ? 'row-error'
            : p.data?.warnings && p.data.warnings.length > 0
              ? 'row-warn'
              : undefined,
      tooltipShowDelay: 300,
      suppressColumnVirtualisation: true,
    });
    gridApi.current = api;
    return () => {
      api.destroy();
      gridApi.current = null;
    };
  }, []);

  useEffect(() => {
    const api = gridApi.current;
    if (!api) return;
    api.setGridOption('rowData', data?.rows ?? []);
    api.setGridOption(
      'pinnedBottomRowData',
      data ? [{ total: true, product: 'Total', ...data.totals }] : [],
    );
  }, [data]);

  const calculate = async () => {
    const ticket = ++latest.current;
    setLoading(true);
    setErrors(NO_ERRORS);
    try {
      const r = await pnl(fromId, toId);
      if (ticket !== latest.current) return;
      setData(r);
    } catch (e) {
      if (ticket !== latest.current) return;
      setData(null);
      if (e instanceof ApiError && (e.field === 'from' || e.field === 'to')) {
        setErrors({ ...NO_ERRORS, [e.field]: e.message });
      } else {
        setErrors({
          ...NO_ERRORS,
          general: e instanceof ApiError ? e.message : 'No se pudo conectar con el backend',
        });
      }
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  };

  const options = useMemo(
    () =>
      snapshots.map((s) => (
        <option key={s.id} value={s.id}>
          {optionLabel(s)}
        </option>
      )),
    [snapshots],
  );

  const failed = data?.rows.filter((r) => r.error).length ?? 0;

  return (
    <section className="pnl" data-testid="pnl-panel">
      <div className="pnl__controls">
        <div className="pnl__field">
          <label className="pnl__label">
            Desde
            <select
              className="pnl__select"
              value={fromId}
              aria-invalid={errors.from ? true : undefined}
              onChange={(e) => setFromPick(e.target.value)}
            >
              {fromId === '' && <option value="">Elige un snapshot</option>}
              {options}
            </select>
          </label>
          {errors.from && (
            <p className="pnl__error" role="alert">
              {errors.from}
            </p>
          )}
        </div>
        <div className="pnl__field">
          <label className="pnl__label">
            Hasta
            <select
              className="pnl__select"
              value={toId}
              aria-invalid={errors.to ? true : undefined}
              onChange={(e) => setToPick(e.target.value)}
            >
              {toId === '' && <option value="">Elige un snapshot</option>}
              {options}
            </select>
          </label>
          {errors.to && (
            <p className="pnl__error" role="alert">
              {errors.to}
            </p>
          )}
        </div>
        <button
          type="button"
          className="pnl__btn"
          disabled={!fromId || !toId || loading}
          onClick={() => void calculate()}
        >
          {loading ? 'Calculando…' : 'Calcular'}
        </button>
        {data && (
          <span className="pnl__meta">
            {fmtDate(data.from.as_of)} → {fmtDate(data.to.as_of)} · MXN
            {failed > 0 && <span className="pnl__warn"> · {failed} con error</span>}
          </span>
        )}
      </div>
      {errors.general && (
        <div className="pnl__banner" role="alert">
          {errors.general}
        </div>
      )}
      <div ref={gridEl} className="pnl__grid" />
    </section>
  );
}
