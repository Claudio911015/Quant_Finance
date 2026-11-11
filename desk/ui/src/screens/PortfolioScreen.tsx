import { useCallback, useEffect, useRef, useState } from 'react';
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
import { ApiError, deleteTrade, valuation } from '../api/client';
import type { ValuationResponse, ValuationRow } from '../api/types';
import { fmtDate, fmtNumber } from '../lib/format';
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

const EXPORT_COLUMNS = ['id', 'product', 'counterparty', 'notional', 'currency', 'maturity', 'pv_mxn'];

const numberCell = { type: 'rightAligned', cellClass: 'num', filter: 'agNumberColumnFilter' } as const;

const columnDefs: ColDef<GridRow>[] = [
  { colId: 'id', field: 'id', headerName: 'ID', width: 72, ...numberCell },
  { colId: 'product', field: 'product', headerName: 'Producto', width: 140 },
  { colId: 'counterparty', field: 'counterparty', headerName: 'Contraparte', flex: 1, minWidth: 160 },
  {
    colId: 'notional',
    field: 'notional',
    headerName: 'Nocional',
    width: 150,
    valueFormatter: (p) => (p.value == null ? '' : fmtNumber(p.value, 2)),
    ...numberCell,
  },
  { colId: 'currency', field: 'currency', headerName: 'Moneda', width: 90 },
  {
    colId: 'maturity',
    field: 'maturity',
    headerName: 'Vencimiento',
    width: 120,
    cellClass: 'num',
    valueFormatter: (p) => (p.value == null ? '' : fmtDate(p.value)),
  },
  {
    colId: 'pv_mxn',
    field: 'pv_mxn',
    headerName: 'PV MXN',
    width: 160,
    valueFormatter: (p) => (p.data?.error ? 'Error' : p.value == null ? '' : fmtNumber(p.value, 2)),
    cellClassRules: {
      'portfolio__neg': (p) => typeof p.value === 'number' && p.value < 0,
      'portfolio__cell-error': (p) => !!p.data?.error,
    },
    ...numberCell,
  },
  {
    colId: 'actions',
    headerName: '',
    width: 84,
    sortable: false,
    filter: false,
    resizable: false,
    cellRenderer: (p: ICellRendererParams<GridRow>) => {
      if (p.data?.id == null) return '';
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'portfolio__del';
      b.textContent = 'Borrar';
      b.setAttribute('aria-label', `Borrar operación ${p.data.id}`);
      return b;
    },
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
  const gridEl = useRef<HTMLDivElement>(null);
  const gridApi = useRef<GridApi<GridRow> | null>(null);
  const onDelete = useRef<(row: GridRow) => void>(() => {});
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

  onDelete.current = async (row) => {
    if (row.id == null) return;
    if (!window.confirm(`¿Borrar la operación ${row.id} (${row.product}, ${row.counterparty})?`)) return;
    try {
      await deleteTrade(row.id);
      await load();
    } catch (e) {
      setError(describe(e));
    }
  };

  useEffect(() => {
    const api = createGrid<GridRow>(gridEl.current!, {
      theme,
      columnDefs,
      localeText: LOCALE_TEXT,
      defaultColDef: {
        sortable: true,
        filter: true,
        useValueFormatterForExport: false,
        tooltipValueGetter: (p) => p.data?.error ?? undefined,
      },
      rowData: [],
      pinnedBottomRowData: [],
      getRowId: (p) => (p.data.total ? 'total' : String(p.data.id)),
      getRowClass: (p) => (p.data?.total ? 'row-total' : p.data?.error ? 'row-error' : undefined),
      tooltipShowDelay: 300,
      suppressColumnVirtualisation: true,
      onCellClicked: (e) => {
        const target = e.event?.target as HTMLElement | null | undefined;
        if (e.data && target?.closest('.portfolio__del')) onDelete.current(e.data);
      },
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
      data ? [{ total: true, product: 'Total', pv_mxn: data.total_mxn }] : [],
    );
  }, [data]);

  const rows = data?.rows ?? [];
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
                ? `${rows.length} operaciones · al ${fmtDate(data.as_of)}`
                : ''}
            {failed > 0 && <span className="portfolio__warn"> · {failed} con error</span>}
          </span>
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
