import {
  AllCommunityModule,
  ModuleRegistry,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
} from 'ag-grid-community';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, createTrade, price } from '../../api/client';
import type { Cashflow, PriceResponse, ProductId, Trade, XccyCashflow } from '../../api/types';
import { FLOW_KIND_EXTRA_LABEL, LEG_LABEL, NO_CSA_TEXT } from '../../lib/csaLabels';
import { fmtDate, fmtMoney, fmtNumber, fmtRate } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import { PricerChart, cashflowsByLeg, payoffText, type ChartData, type PayoffSeries } from './PricerChart';
import type { FieldSpec, ProductSpec } from './types';
import './PricerForm.css';

ModuleRegistry.registerModules([AllCommunityModule]);

interface Result {
  /** Parámetros enviados (sin snapshot): la gráfica y "revaluar" parten de estos, no del formulario. */
  params: Record<string, unknown>;
  response: PriceResponse;
}

const RISK_LABELS: Record<string, { label: string; fmt: (v: number) => string }> = {
  dv01: { label: 'DV01', fmt: (v) => fmtNumber(v, 2) },
  par_rate: { label: 'Tasa par', fmt: fmtRate },
  forward: { label: 'Forward', fmt: (v) => fmtNumber(v, 4) },
  vol: { label: 'Volatilidad', fmt: fmtRate },
  delta: { label: 'Delta', fmt: (v) => fmtNumber(v, 4) },
  gamma: { label: 'Gamma', fmt: (v) => fmtNumber(v, 4) },
  vega: { label: 'Vega (por 1 pt de vol)', fmt: (v) => fmtNumber(v, 4) },
  theta: { label: 'Theta', fmt: (v) => fmtNumber(v, 4) },
  rho: { label: 'Rho', fmt: (v) => fmtNumber(v, 4) },
  duration: { label: 'Duración', fmt: (v) => fmtNumber(v, 4) },
  convexity: { label: 'Convexidad', fmt: (v) => fmtNumber(v, 4) },
  // --- corte 3 --- cross currency swap
  par_spread: { label: 'Diferencial par', fmt: (v) => `${fmtNumber(v * 10000, 2)} pb` },
  dv01_mxn_usd: { label: 'DV01 MXN-USD', fmt: (v) => fmtNumber(v, 2) },
  dv01_tiie: { label: 'DV01 TIIE-F', fmt: (v) => fmtNumber(v, 2) },
  dv01_sofr: { label: 'DV01 SOFR', fmt: (v) => fmtNumber(v, 2) },
  // --- fin corte 3 ---
};

/** Datos del cálculo de los exóticos de FX (`details` del backend); solo se muestran los que vengan. */
const DETAIL_LABELS: Record<string, { label: string; fmt: (v: unknown) => string }> = {
  price_pct: { label: 'Precio (% del pago)', fmt: (v) => `${fmtNumber(Number(v), 2)} %` },
  no_touch_probability: { label: 'Probabilidad de no tocar', fmt: (v) => `${fmtNumber(Number(v) * 100, 2)} %` },
  analytic_flat_pv: { label: 'Referencia analítica (plano)', fmt: (v) => fmtMoney(Number(v), 'MXN') },
  paths: { label: 'Trayectorias', fmt: (v) => fmtNumber(Number(v), 0) },
  model: { label: 'Modelo', fmt: (v) => (v === 'flat' ? 'Plano' : 'Con sonrisa (vol local)') },
  method: { label: 'Método', fmt: (v) => (v === 'analytic' ? 'Analítico' : 'Monte Carlo') },
};

/** Productos que solo se valúan: no se agregan al portafolio. */
const NOT_TRADABLE: ProductId[] = ['fx_no_touch', 'fx_double_no_touch'];

/** Texto inicial de un campo: miles con coma en montos, sin ceros de relleno. */
export function initialText(f: FieldSpec): string {
  if (f.default === null) return '';
  if (typeof f.default === 'string') return f.default;
  return f.default.toLocaleString('en-US', {
    maximumFractionDigits: 10,
    useGrouping: f.kind !== 'percent',
  });
}

/** Decimal → texto de un campo percent (0.0671234 → "6.71234"), con la precisión que `parseParams` conserva. */
function percentText(dec: number): string {
  return (dec * 100).toLocaleString('en-US', { maximumFractionDigits: 10, useGrouping: false });
}

/** Convierte el texto de los campos en el cuerpo de la petición (percent: % → decimal). */
export function parseParams(spec: ProductSpec, values: Record<string, string>) {
  const params: Record<string, unknown> = {};
  const errors: Record<string, string> = {};
  for (const f of spec.fields) {
    const raw = (values[f.name] ?? '').trim();
    if (raw === '') {
      if (!f.optional) errors[f.name] = 'Campo obligatorio';
      continue;
    }
    if (f.kind === 'select' || f.kind === 'text') {
      params[f.name] = raw;
      continue;
    }
    const n = Number(raw.replace(/[,\s]/g, ''));
    if (!Number.isFinite(n)) {
      errors[f.name] = 'Debe ser un número';
      continue;
    }
    params[f.name] = f.kind === 'percent' ? Number((n / 100).toPrecision(12)) : n;
  }
  return { params, errors };
}

const GRID_THEME = themeQuartz.withParams({
  backgroundColor: 'var(--bg)',
  foregroundColor: 'var(--text)',
  headerBackgroundColor: 'var(--bg-elev)',
  headerTextColor: 'var(--text-dim)',
  borderColor: 'var(--border)',
  rowHoverColor: 'var(--bg-hover)',
  accentColor: 'var(--accent)',
  fontFamily: 'var(--font-sans)',
  fontSize: 12,
  headerFontSize: 11,
  rowHeight: 26,
  headerHeight: 28,
  wrapperBorderRadius: 4,
});

// --- corte 3 --- la tabla del cross currency swap tiene seis columnas en ~560 px: menos relleno por celda
const XCCY_GRID_THEME = GRID_THEME.withParams({ cellHorizontalPadding: 8 });
// --- fin corte 3 ---

const CASHFLOW_COLUMNS: ColDef<Cashflow>[] = [
  { headerName: 'Fecha', field: 'date', minWidth: 116, flex: 1.2 },
  { headerName: 'Días', field: 'days', minWidth: 64, flex: 0.6, cellClass: 'num', headerClass: 'ag-right-aligned-header' },
  {
    headerName: 'Monto',
    field: 'amount',
    minWidth: 120,
    flex: 1.4,
    cellClass: 'num',
    headerClass: 'ag-right-aligned-header',
    valueFormatter: (p) => fmtNumber(p.value, 2),
  },
  {
    headerName: 'Factor desc.',
    field: 'df',
    minWidth: 110,
    flex: 1.2,
    cellClass: 'num',
    headerClass: 'ag-right-aligned-header',
    valueFormatter: (p) => fmtNumber(p.value, 6),
  },
  {
    headerName: 'VP',
    field: 'pv',
    minWidth: 120,
    flex: 1.4,
    cellClass: 'num',
    headerClass: 'ag-right-aligned-header',
    valueFormatter: (p) => fmtNumber(p.value, 2),
  },
];

// --- corte 3 --- flujos del cross currency swap: pata y tipo, y VP en MXN (los montos van en la moneda de su pata)
const XCCY_KIND_LABEL: Record<XccyCashflow['kind'], string> = {
  coupon: 'Cupón',
  exchange: FLOW_KIND_EXTRA_LABEL.exchange,
};

const legOf = (c: Cashflow | undefined) => (c as Partial<XccyCashflow> | undefined)?.leg;

const XCCY_COLUMNS: ColDef<Cashflow>[] = [
  { headerName: 'Fecha', field: 'date', minWidth: 80, flex: 1 },
  {
    headerName: 'Pata',
    colId: 'leg',
    valueGetter: (p) => legOf(p.data),
    valueFormatter: (p) => (p.value ? LEG_LABEL[p.value as 'USD' | 'MXN'] : '—'),
    minWidth: 94,
    flex: 1.6,
    wrapText: true,
    autoHeight: true,
  },
  {
    headerName: 'Tipo',
    colId: 'kind',
    valueGetter: (p) => (p.data as Partial<XccyCashflow> | undefined)?.kind,
    valueFormatter: (p) => XCCY_KIND_LABEL[p.value as XccyCashflow['kind']] ?? '—',
    minWidth: 88,
    flex: 1.2,
    wrapText: true,
    autoHeight: true,
  },
  {
    headerName: 'Monto',
    field: 'amount',
    minWidth: 100,
    flex: 1.2,
    cellClass: 'num',
    headerClass: 'ag-right-aligned-header',
    valueFormatter: (p) => fmtNumber(p.value, 2),
  },
  {
    headerName: 'Factor desc.',
    field: 'df',
    minWidth: 76,
    flex: 0.9,
    cellClass: 'num',
    headerClass: 'ag-right-aligned-header',
    valueFormatter: (p) => fmtNumber(p.value, 6),
  },
  {
    headerName: 'VP (MXN)',
    colId: 'pv_mxn',
    valueGetter: (p) => (p.data as Partial<XccyCashflow> | undefined)?.pv_mxn,
    minWidth: 100,
    flex: 1.2,
    cellClass: 'num',
    headerClass: 'ag-right-aligned-header',
    valueFormatter: (p) => (typeof p.value === 'number' ? fmtNumber(p.value, 2) : '—'),
  },
];
// --- fin corte 3 ---

function CashflowGrid({ rows }: { rows: Cashflow[] }) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<GridApi<Cashflow> | null>(null);
  const withLegs = rows.some((r) => legOf(r) != null);
  const columns = withLegs ? XCCY_COLUMNS : CASHFLOW_COLUMNS;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const grid = createGrid<Cashflow>(el, {
      theme: withLegs ? XCCY_GRID_THEME : GRID_THEME,
      columnDefs: columns,
      rowData: rows,
      suppressCellFocus: true,
    });
    api.current = grid;
    return () => {
      grid.destroy();
      api.current = null;
    };
    // la creación es única; los cambios de filas van por el efecto siguiente
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api.current?.setGridOption('rowData', rows);
  }, [rows]);

  useEffect(() => {
    api.current?.setGridOption('columnDefs', columns);
    api.current?.setGridOption('theme', withLegs ? XCCY_GRID_THEME : GRID_THEME);
  }, [columns, withLegs]);

  return <div ref={host} className="pricer__grid" aria-label="Tabla de flujos" />;
}

// --- corte 3 --- detalle del cross currency swap: nocional MXN, tipo de cambio y curva de descuento
function XccyDetails({ details }: { details: Record<string, unknown> }) {
  const { notional_mxn: notionalMxn, fx_rate: fxRate, discount_curve: curve } = details;
  return (
    <section className="pricer__block">
      <h2 className="pricer__caption">Detalle del swap</h2>
      <table className="pricer__table">
        <tbody>
          {typeof notionalMxn === 'number' && (
            <tr>
              <th scope="row">Nocional MXN</th>
              <td className="num">{fmtMoney(notionalMxn, 'MXN')}</td>
            </tr>
          )}
          {typeof fxRate === 'number' && (
            <tr>
              <th scope="row">Tipo de cambio</th>
              <td className="num">{fmtNumber(fxRate, 4)}</td>
            </tr>
          )}
        </tbody>
      </table>
      {curve === 'TIIE-F' ? (
        <p className="pricer__warn" role="status">
          {NO_CSA_TEXT}
        </p>
      ) : (
        typeof curve === 'string' && <p className="pricer__note">Curva de descuento: {curve}</p>
      )}
    </section>
  );
}
// --- fin corte 3 ---

function ResultView({ spec, result }: { spec: ProductSpec; result: Result }) {
  const { response, params } = result;
  const { currency, pv, pv_mxn: pvMxn, risk, cashflows, details } = response;
  const { snapshot } = useSnapshot();
  // Cap/floor y swaption necesitan el periodo de pago de su curva para la gráfica de payoff.
  const periodDays = snapshot?.curves[String(params.curve)]?.period_days;

  const chart = useMemo<ChartData | null>(() => {
    if (spec.chart === 'cashflows' && cashflows && cashflows.length > 0) {
      return { kind: 'cashflows', cashflows, currency };
    }
    if (spec.chart === 'payoff') {
      const series = details?.chart as PayoffSeries | undefined; // solo los exóticos con barrera la traen
      return { kind: 'payoff', product: spec.product, params, pv, currency, periodDays, series };
    }
    return null;
  }, [spec.chart, spec.product, cashflows, params, pv, currency, periodDays, details]);
  const note = chart?.kind === 'payoff' ? payoffText(chart.product).note : undefined;

  const riskRows = Object.entries(risk ?? {});
  const detailRows = Object.entries(DETAIL_LABELS).filter(([key]) => details?.[key] !== undefined);
  const stdError = Number(details?.std_error);
  const byLeg = chart?.kind === 'cashflows' && cashflowsByLeg(chart.cashflows) !== null; // corte 3

  return (
    <>
      <div className="pricer__stats">
        <div className="pricer__stat">
          <span className="pricer__caption">Valor presente</span>
          <span className={`num pricer__pv${pv < 0 ? ' pricer__pv--neg' : ''}`}>{fmtMoney(pv, currency)}</span>
          {stdError > 0 && <span className="pricer__note">{`± ${fmtMoney(stdError, 'MXN')} (error estándar)`}</span>}
        </div>
        <div className="pricer__stat">
          <span className="pricer__caption">Valor presente en MXN</span>
          <span className={`num pricer__pv${pvMxn < 0 ? ' pricer__pv--neg' : ''}`}>{fmtMoney(pvMxn, 'MXN')}</span>
        </div>
      </div>

      {spec.product === 'xccy_swap' && <XccyDetails details={response.details ?? {}} />}

      {riskRows.length > 0 && (
        <section className="pricer__block">
          <h2 className="pricer__caption">Medidas de riesgo</h2>
          <table className="pricer__table">
            <tbody>
              {riskRows.map(([key, value]) => {
                const meta = RISK_LABELS[key];
                return (
                  <tr key={key}>
                    <th scope="row">{meta?.label ?? key}</th>
                    <td className="num">
                      {typeof value === 'number' ? (meta ? meta.fmt(value) : fmtNumber(value, 4)) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      {detailRows.length > 0 && (
        <section className="pricer__block">
          <h2 className="pricer__caption">Detalle del cálculo</h2>
          <table className="pricer__table">
            <tbody>
              {detailRows.map(([key, meta]) => (
                <tr key={key}>
                  <th scope="row">{meta.label}</th>
                  <td className="num">{details[key] === null ? '—' : meta.fmt(details[key])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {chart && (
        <section className="pricer__block">
          <h2 className="pricer__caption">
            {chart.kind === 'cashflows'
              ? byLeg
                ? 'VP de los flujos por pata (MXN)'
                : 'Perfil de flujos'
              : payoffText(chart.product).title}
          </h2>
          <PricerChart data={chart} />
          {note && <p className="pricer__note">{note}</p>}
        </section>
      )}

      {cashflows && cashflows.length > 0 && (
        <section className="pricer__block">
          <h2 className="pricer__caption">Flujos</h2>
          <CashflowGrid rows={cashflows} />
        </section>
      )}
    </>
  );
}

export function Field({
  spec,
  field,
  value,
  error,
  onChange,
}: {
  spec: ProductSpec;
  field: FieldSpec;
  value: string;
  error?: string;
  onChange: (v: string) => void;
}) {
  const id = `pricer-${spec.product}-${field.name}`;
  const noteId = `${id}-note`;
  const note = error ?? field.help;
  const common = {
    id,
    value,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': note ? noteId : undefined,
  };

  return (
    <div className="pricer__field">
      <label htmlFor={id}>{field.label}</label>
      {field.kind === 'select' ? (
        <select {...common} className="pricer__input" onChange={(e) => onChange(e.target.value)}>
          {(field.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <div className="pricer__input-wrap">
          <input
            {...common}
            type="text"
            inputMode={field.kind === 'text' ? 'text' : 'decimal'}
            autoComplete="off"
            className={`pricer__input${field.kind === 'text' ? '' : ' num'}`}
            onChange={(e) => onChange(e.target.value)}
          />
          {field.kind === 'percent' && <span className="pricer__suffix">%</span>}
        </div>
      )}
      {note &&
        (error ? (
          <div id={noteId} className="pricer__error" role="alert">
            {error}
          </div>
        ) : (
          <div id={noteId} className="pricer__help">
            {note}
          </div>
        ))}
    </div>
  );
}

function DateField({
  id,
  label,
  value,
  error,
  help,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  error?: string;
  help?: string;
  onChange: (v: string) => void;
}) {
  const noteId = `${id}-note`;
  const note = error ?? help;
  return (
    <div className="pricer__field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="date"
        className="pricer__input"
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? noteId : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {note &&
        (error ? (
          <div id={noteId} className="pricer__error" role="alert">
            {error}
          </div>
        ) : (
          <div id={noteId} className="pricer__help">
            {note}
          </div>
        ))}
    </div>
  );
}

const DATE_FIELDS = ['trade_date', 'start_date', 'maturity_date'];

export function PricerForm({ spec }: { spec: ProductSpec }) {
  const { snapshotId, snapshots, snapshot } = useSnapshot();
  // Pacto e inicio siguen al `as_of` del snapshot activo mientras el usuario no los edite.
  const asOf = snapshots.find((s) => s.id === snapshotId)?.as_of ?? snapshot?.as_of ?? '';
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(spec.fields.map((f) => [f.name, initialText(f)])),
  );
  const [counterparty, setCounterparty] = useState('');
  const [tradeEdit, setTradeEdit] = useState<string | null>(null);
  const [startEdit, setStartEdit] = useState<string | null>(null);
  const [maturity, setMaturity] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState<{ trade: Trade; requestedMaturity: string } | null>(null);
  const tradeDate = tradeEdit ?? asOf;
  const startDate = startEdit ?? asOf;
  // Cada valuación toma un número; solo la última puede escribir estado.
  const ticket = useRef(0);
  const resultRef = useRef<Result | null>(null);

  const report = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError) {
        const known =
          e.field !== null &&
          (e.field === 'counterparty' || DATE_FIELDS.includes(e.field) || spec.fields.some((f) => f.name === e.field));
        if (known) setFieldErrors({ [e.field as string]: e.message });
        else setBanner(e.message);
      } else {
        setBanner('No se pudo conectar con el backend');
      }
    },
    [spec.fields],
  );

  const run = useCallback(
    async (params: Record<string, unknown>) => {
      const mine = ++ticket.current;
      setPending(true);
      setBanner(null);
      setFieldErrors({});
      try {
        const response = await price(spec.product, { ...params, snapshot: snapshotId });
        if (mine !== ticket.current) return;
        resultRef.current = { params, response };
        setResult(resultRef.current);
        // Un porcentaje opcional en blanco (tasa fija del irs = tasa par) se rellena con lo que el
        // backend usó: "Agregar al portafolio" necesita el valor explícito.
        const used: Record<string, string> = {};
        for (const f of spec.fields) {
          const v = response.details?.[f.name];
          if (f.kind === 'percent' && f.optional && params[f.name] === undefined && typeof v === 'number') {
            used[f.name] = percentText(v);
          }
        }
        if (Object.keys(used).length > 0) setValues((prev) => ({ ...prev, ...used }));
      } catch (e) {
        if (mine !== ticket.current) return;
        resultRef.current = null;
        setResult(null);
        report(e);
      } finally {
        if (mine === ticket.current) setPending(false);
      }
    },
    [spec.product, spec.fields, snapshotId, report],
  );

  // Al cambiar de snapshot se revalúa lo que ya está en pantalla.
  useEffect(() => {
    if (resultRef.current) void run(resultRef.current.params);
    // solo reacciona al snapshot; `run` cambia con él
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshotId]);

  const onValuate = (e: FormEvent) => {
    e.preventDefault();
    setAdded(null);
    const { params, errors } = parseParams(spec, values);
    if (Object.keys(errors).length > 0) {
      setBanner(null);
      setFieldErrors(errors);
      return;
    }
    void run(params);
  };

  const onAdd = async (e: FormEvent) => {
    e.preventDefault();
    setAdded(null);
    const { params, errors } = parseParams(spec, values);
    if (Object.keys(errors).length > 0) {
      setBanner(null);
      setFieldErrors(errors);
      return;
    }
    setBanner(null);
    setFieldErrors({});
    setAdding(true);
    try {
      const trade = await createTrade({
        product: spec.product,
        counterparty: counterparty.trim(),
        params,
        ...(tradeDate ? { trade_date: tradeDate } : {}),
        ...(startDate ? { start_date: startDate } : {}),
        ...(maturity ? { maturity_date: maturity } : {}),
      });
      setAdded({ trade, requestedMaturity: maturity });
    } catch (err) {
      report(err);
    } finally {
      setAdding(false);
    }
  };

  const setDate = (name: string, set: (v: string) => void) => (v: string) => {
    set(v);
    setFieldErrors(({ [name]: _gone, ...rest }) => rest);
  };

  const setValue = (name: string, v: string) => {
    setValues((prev) => ({ ...prev, [name]: v }));
    setFieldErrors(({ [name]: _gone, ...rest }) => rest);
  };

  return (
    <div className="pricer">
      <div className="pricer__side">
        <form className="pricer__panel" onSubmit={onValuate} noValidate aria-label="Parámetros">
          <h1>{spec.title}</h1>
          {spec.fields.map((f) => (
            <Field
              key={f.name}
              spec={spec}
              field={f}
              value={values[f.name] ?? ''}
              error={fieldErrors[f.name]}
              onChange={(v) => setValue(f.name, v)}
            />
          ))}
          <button type="submit" className="pricer__btn pricer__btn--primary" disabled={pending}>
            {pending ? 'Valuando…' : 'Valuar'}
          </button>
        </form>

        {!NOT_TRADABLE.includes(spec.product) && (
          <form className="pricer__panel" onSubmit={onAdd} noValidate aria-label="Portafolio">
            <div className="pricer__field">
              <label htmlFor="pricer-counterparty">Contraparte</label>
              <input
                id="pricer-counterparty"
                type="text"
                autoComplete="off"
                className="pricer__input"
                value={counterparty}
                aria-invalid={fieldErrors.counterparty ? true : undefined}
                aria-describedby={fieldErrors.counterparty ? 'pricer-counterparty-note' : undefined}
                onChange={(e) => {
                  setCounterparty(e.target.value);
                  setFieldErrors(({ counterparty: _gone, ...rest }) => rest);
                }}
              />
              {fieldErrors.counterparty && (
                <div id="pricer-counterparty-note" className="pricer__error" role="alert">
                  {fieldErrors.counterparty}
                </div>
              )}
            </div>
            <DateField
              id="pricer-trade-date"
              label="Fecha de pacto"
              value={tradeDate}
              error={fieldErrors.trade_date}
              onChange={setDate('trade_date', setTradeEdit)}
            />
            <DateField
              id="pricer-start-date"
              label="Inicio"
              value={startDate}
              error={fieldErrors.start_date}
              onChange={setDate('start_date', setStartEdit)}
            />
            <DateField
              id="pricer-maturity-date"
              label="Vencimiento"
              value={maturity}
              error={fieldErrors.maturity_date}
              help="Vacío: se calcula con el plazo"
              onChange={setDate('maturity_date', setMaturity)}
            />
            <button type="submit" className="pricer__btn" disabled={adding}>
              {adding ? 'Agregando…' : 'Agregar al portafolio'}
            </button>
            {added && (
              <div className="pricer__ok" role="status">
                <span>
                  Operación {added.trade.id} agregada. <Link to="/portafolio">Ver portafolio</Link> ·{' '}
                  <Link to={`/portafolio/${added.trade.id}`}>Ver ficha</Link>
                </span>
                <span>
                  {added.requestedMaturity !== '' && added.requestedMaturity !== added.trade.maturity_date
                    ? 'Vencimiento ajustado'
                    : 'Vencimiento'}
                  : <span className="num">{fmtDate(added.trade.maturity_date)}</span>
                </span>
              </div>
            )}
          </form>
        )}
      </div>

      <div className="pricer__result">
        {banner && (
          <div className="pricer__banner" role="alert">
            {banner}
          </div>
        )}
        {result ? (
          <ResultView spec={spec} result={result} />
        ) : (
          !banner && <p className="pricer__empty">Captura los parámetros y presiona Valuar (Enter).</p>
        )}
      </div>
    </div>
  );
}
