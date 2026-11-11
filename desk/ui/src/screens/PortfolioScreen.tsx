import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDark,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
  type ICellRendererParams,
} from 'ag-grid-community';
import { ApiError, valuation } from '../api/client';
import type { TradeStatus, ValuationResponse, ValuationRow } from '../api/types';
import { fmtDate, fmtMoney, fmtNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import PnlPanel from './PnlPanel';
import './PortfolioScreen.css';

ModuleRegistry.registerModules([AllCommunityModule]);

/** Fila del blotter: una operación valuada o la fila fija de total. */
type GridRow = Partial<Omit<ValuationRow, 'product'>> & { product?: string; total?: boolean };

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

const LOCALE_TEXT: Record<string, string> = {
  noRowsToShow: 'Sin operaciones. Agrega una desde Pricers.',
  filterOoo: 'Filtrar...',
  equals: 'Igual a',
  notEqual: 'Distinto de',
  contains: 'Contiene',
  notContains: 'No contiene',
  startsWith: 'Empieza con',
  endsWith: 'Termina con',
  lessThan: 'Menor que',
  lessThanOrEqual: 'Menor o igual que',
  greaterThan: 'Mayor que',
  greaterThanOrEqual: 'Mayor o igual que',
  inRange: 'En el rango',
  inRangeStart: 'Desde',
  inRangeEnd: 'Hasta',
  blank: 'Vacío',
  notBlank: 'No vacío',
  andCondition: 'Y',
  orCondition: 'O',
  applyFilter: 'Aplicar',
  resetFilter: 'Restablecer',
  clearFilter: 'Limpiar',
  searchOoo: 'Buscar...',
};

const EXPORT_COLUMNS = [
  'id',
  'product',
  'counterparty',
  'notional',
  'currency',
  'trade_date',
  'maturity_date',
  'status',
  'pv_mxn',
];

const STATUS_LABEL: Record<TradeStatus, string> = {
  no_pactada: 'No pactada',
  viva: 'Viva',
  vencida: 'Vencida',
  terminada: 'Terminada',
  ejercida: 'Ejercida',
};
const STATUS_ORDER: TradeStatus[] = ['no_pactada', 'viva', 'vencida', 'terminada', 'ejercida'];

type StatusFilter = 'all' | TradeStatus;

/** `pv` viaja en la moneda de /api/price: MXN para FX y renta variable, la de la curva en el resto. */
const PV_IN_MXN = new Set(['fx_forward', 'fx_option', 'equity_option']);

function pvCurrency(row: GridRow): string {
  return row.product && PV_IN_MXN.has(row.product) ? 'MXN' : (row.currency ?? 'MXN');
}

/** Tooltip de una fila: el error de valuación, o los avisos de la valuación. */
export function rowTooltip(row: GridRow | undefined): string | undefined {
  if (!row) return undefined;
  if (row.error) return row.error;
  const messages = (row.warnings ?? []).map((w) => w.message);
  return messages.length > 0 ? messages.join(' · ') : undefined;
}

/** Destino del clic en un id; lo fija PortfolioScreen con su `navigate`. */
const openTrade: { current: (path: string) => void } = { current: () => {} };

const numberCell = { type: 'rightAligned', cellClass: 'num', filter: 'agNumberColumnFilter' } as const;

/** Exportadas para la prueba de anchos: la suma de los anchos mínimos debe caber en 1280 px. */
export const columnDefs: ColDef<GridRow>[] = [
  {
    colId: 'id',
    field: 'id',
    headerName: 'ID',
    width: 56,
    // El id es un enlace real (clic derecho, nueva pestaña); el clic simple navega sin recargar.
    cellRenderer: (p: ICellRendererParams<GridRow>) => {
      if (p.data?.id == null) return '';
      const a = document.createElement('a');
      a.href = `/portafolio/${p.data.id}`;
      a.textContent = String(p.data.id);
      a.addEventListener('click', (ev) => {
        if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
        ev.preventDefault();
        openTrade.current(a.getAttribute('href') ?? '');
      });
      return a;
    },
    ...numberCell,
  },
  { colId: 'product', field: 'product', headerName: 'Producto', width: 92 },
  { colId: 'counterparty', field: 'counterparty', headerName: 'Contraparte', flex: 1, minWidth: 148 },
  {
    colId: 'notional',
    field: 'notional',
    headerName: 'Nocional',
    width: 110,
    valueFormatter: (p) => (p.value == null ? '' : fmtNumber(p.value, 2)),
    ...numberCell,
  },
  { colId: 'currency', field: 'currency', headerName: 'Moneda', width: 84 },
  {
    colId: 'trade_date',
    field: 'trade_date',
    headerName: 'Pacto',
    width: 96,
    cellClass: 'num',
    valueFormatter: (p) => (p.value == null ? '' : fmtDate(p.value)),
  },
  {
    colId: 'maturity_date',
    field: 'maturity_date',
    headerName: 'Vencimiento',
    width: 110,
    cellClass: 'num',
    valueFormatter: (p) => (p.value == null ? '' : fmtDate(p.value)),
  },
  {
    colId: 'status',
    field: 'status',
    headerName: 'Estado',
    width: 96,
    filter: false, // el selector de arriba filtra por estado
    valueFormatter: (p) => (p.value == null ? '' : (STATUS_LABEL[p.value as TradeStatus] ?? p.value)),
  },
  {
    colId: 'pv',
    field: 'pv',
    headerName: 'PV',
    width: 118,
    valueFormatter: (p) =>
      p.data?.error ? 'Error' : p.value == null || !p.data ? '' : fmtMoney(p.value, pvCurrency(p.data)),
    cellClassRules: {
      'portfolio__neg': (p) => typeof p.value === 'number' && p.value < 0,
      'portfolio__cell-error': (p) => !!p.data?.error,
    },
    ...numberCell,
  },
  {
    colId: 'pv_mxn',
    field: 'pv_mxn',
    headerName: 'PV MXN',
    width: 108,
    valueFormatter: (p) => (p.data?.error ? 'Error' : p.value == null ? '' : fmtNumber(p.value, 2)),
    cellClassRules: {
      'portfolio__neg': (p) => typeof p.value === 'number' && p.value < 0,
      'portfolio__cell-error': (p) => !!p.data?.error,
    },
    ...numberCell,
  },
];

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

export function PortfolioScreen() {
  const { snapshotId } = useSnapshot();
  const [data, setData] = useState<ValuationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'blotter' | 'pnl'>('blotter');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const navigate = useNavigate();
  const gridEl = useRef<HTMLDivElement>(null);
  const gridApi = useRef<GridApi<GridRow> | null>(null);
  // Cada carga toma un número; solo la última escribe estado (una respuesta lenta de un
  // snapshot anterior no debe pisar la del que el usuario eligió después).
  const latest = useRef(0);

  const load = useCallback(async () => {
    const ticket = ++latest.current;
    setLoading(true);
    try {
      const v = await valuation(snapshotId);
      if (ticket !== latest.current) return;
      setData(v);
      setError(null);
    } catch (e) {
      if (ticket !== latest.current) return;
      setData(null);
      setError(describe(e));
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  }, [snapshotId]);

  useEffect(() => {
    void load();
  }, [load]);

  openTrade.current = navigate;

  useEffect(() => {
    const api = createGrid<GridRow>(gridEl.current!, {
      theme,
      columnDefs,
      localeText: LOCALE_TEXT,
      defaultColDef: {
        sortable: true,
        filter: true,
        useValueFormatterForExport: false,
        tooltipValueGetter: (p) => rowTooltip(p.data),
      },
      rowData: [],
      pinnedBottomRowData: [],
      getRowId: (p) => (p.data.total ? 'total' : String(p.data.id)),
      getRowClass: (p) =>
        p.data?.total
          ? 'row-total'
          : p.data?.error
            ? 'row-error'
            : p.data?.warnings?.length
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

  const rows = data?.rows ?? [];
  const shown = statusFilter === 'all' ? rows : rows.filter((r) => r.status === statusFilter);

  useEffect(() => {
    const api = gridApi.current;
    if (!api) return;
    // Si el filtro oculta todo, "agrega una desde Pricers" sería falso.
    api.setGridOption(
      'overlayNoRowsTemplate',
      rows.length > 0 && shown.length === 0
        ? '<span class="ag-overlay-no-rows-center">Ninguna operación con ese estado.</span>'
        : undefined,
    );
    api.setGridOption('rowData', shown);
    // El total sigue siendo el del backend (todo el portafolio), no el de las filas visibles.
    api.setGridOption(
      'pinnedBottomRowData',
      data ? [{ total: true, product: 'Total', pv_mxn: data.total_mxn }] : [],
    );
  }, [data, statusFilter]);

  const failed = rows.filter((r) => r.error).length;

  return (
    <section className="portfolio">
      <div className="portfolio__tabs" role="tablist" aria-label="Vistas del portafolio">
        <button
          type="button"
          role="tab"
          id="portfolio-tab-blotter"
          aria-selected={tab === 'blotter'}
          aria-controls="portfolio-panel-blotter"
          className="portfolio__tab"
          onClick={() => setTab('blotter')}
        >
          Operaciones
        </button>
        <button
          type="button"
          role="tab"
          id="portfolio-tab-pnl"
          aria-selected={tab === 'pnl'}
          aria-controls="portfolio-panel-pnl"
          className="portfolio__tab"
          onClick={() => setTab('pnl')}
        >
          P&L
        </button>
      </div>
      {/* El blotter sigue montado al cambiar de pestaña: AG Grid se crea una sola vez. */}
      <div
        role="tabpanel"
        id="portfolio-panel-blotter"
        aria-labelledby="portfolio-tab-blotter"
        className="portfolio__panel"
        hidden={tab !== 'blotter'}
      >
        <header className="portfolio__head">
          <h1>Portafolio</h1>
          <span className="portfolio__meta">
            {loading
              ? 'Cargando…'
              : data
                ? `${shown.length === rows.length ? rows.length : `${shown.length} de ${rows.length}`} operaciones · al ${fmtDate(data.as_of)}`
                : ''}
            {failed > 0 && <span className="portfolio__warn"> · {failed} con error</span>}
          </span>
          <label className="portfolio__filter">
            Estado
            <select
              className="portfolio__select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            >
              <option value="all">Todas</option>
              {STATUS_ORDER.map((st) => (
                <option key={st} value={st}>
                  {STATUS_LABEL[st]}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="portfolio__btn"
            disabled={!data || rows.length === 0}
            onClick={() =>
              gridApi.current?.exportDataAsCsv({ fileName: 'portafolio.csv', columnKeys: EXPORT_COLUMNS })
            }
          >
            Exportar CSV
          </button>
        </header>
        {error && (
          <div className="portfolio__banner" role="alert">
            {error}
          </div>
        )}
        <div ref={gridEl} className="portfolio__grid" />
      </div>
      {tab === 'pnl' && (
        <div
          role="tabpanel"
          id="portfolio-panel-pnl"
          aria-labelledby="portfolio-tab-pnl"
          className="portfolio__panel"
        >
          <PnlPanel />
        </div>
      )}
    </section>
  );
}
