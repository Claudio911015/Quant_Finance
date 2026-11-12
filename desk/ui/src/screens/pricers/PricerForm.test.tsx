import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PriceResponse, XccyCashflow } from '../../api/types';
import { LEG_LABEL, NO_CSA_TEXT } from '../../lib/csaLabels';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { cashflowsByLeg } from './PricerChart';
import { PricerForm } from './PricerForm';
import { PRODUCT_SPECS } from './registry';

// La tabla de flujos se deja crear de verdad; solo se anotan las opciones con que se creó.
const grids = vi.hoisted(() => ({ options: [] as { columnDefs: { headerName: string; valueFormatter?: (p: { value: unknown }) => string }[] }[] }));
vi.mock('ag-grid-community', async (importOriginal) => {
  const actual = await importOriginal<typeof import('ag-grid-community')>();
  return {
    ...actual,
    createGrid: ((el: HTMLElement, options: (typeof grids.options)[number]) => {
      grids.options.push(options);
      return (actual.createGrid as (...a: unknown[]) => unknown)(el, options);
    }) as typeof actual.createGrid,
  };
});

// echarts y AG Grid dependen de medidas de layout que jsdom no tiene; aquí solo importa
// qué datos reciben, no cómo pintan.
vi.mock('./PricerChart', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./PricerChart')>()), // los textos de cada gráfica sí son los reales
  PricerChart: ({ data }: { data: { kind: string; product?: string; periodDays?: number; series?: unknown } }) => (
    <div
      data-testid="chart"
      data-kind={data.kind}
      data-product={data.product}
      data-period-days={data.periodDays}
      data-series={JSON.stringify(data.series)}
    />
  ),
}));

const SNAPSHOTS = [
  { id: 'MX-DEMO', label: 'México demo', synthetic: true, as_of: '2026-11-10' },
  { id: 'ALT', label: 'Alterno', synthetic: false, as_of: '2026-11-11' },
];

const IRS_RESPONSE: PriceResponse = {
  product: 'irs',
  currency: 'MXN',
  pv: 1234.5,
  pv_mxn: 1234.5,
  risk: { dv01: -4567.8, par_rate: 0.0671 },
  cashflows: [{ date: '2026-12-08', days: 28, amount: -1234.5, df: 0.9947, pv: -1228 }],
  details: {},
};

/** Dos cupones y los intercambios del cross currency swap, como los entrega `POST /api/price/xccy_swap`. */
const XCCY_FLOWS: XccyCashflow[] = [
  { date: '2026-12-08', days: 28, leg: 'USD', kind: 'coupon', amount: -30330, df: 0.997, pv: -30240, pv_mxn: -562464 },
  { date: '2026-12-08', days: 28, leg: 'MXN', kind: 'coupon', amount: 1009000, df: 0.995, pv: 1003955, pv_mxn: 1003955 },
  { date: '2027-01-05', days: 56, leg: 'USD', kind: 'coupon', amount: -30000, df: 0.994, pv: -29820, pv_mxn: -554652 },
  { date: '2027-01-05', days: 56, leg: 'USD', kind: 'exchange', amount: 10000000, df: 0.994, pv: 9940000, pv_mxn: 184884000 },
  { date: '2027-01-05', days: 56, leg: 'MXN', kind: 'exchange', amount: -186000000, df: 0.99, pv: -184140000, pv_mxn: -184140000 },
];

const XCCY_RESPONSE: PriceResponse = {
  product: 'xccy_swap',
  currency: 'MXN',
  pv: 12345.6,
  pv_mxn: 12345.6,
  risk: { par_spread: -0.001, dv01_mxn_usd: 1234.5, dv01_tiie: -50.1, dv01_sofr: 980.2 },
  cashflows: XCCY_FLOWS,
  details: { fx_rate: 18.6, spread: -0.001, notional_mxn: 186000000, discount_curve: 'MXN-USD' },
};

interface Call {
  method: string;
  path: string;
  body: Record<string, unknown> | null;
}

/** `fetch` simulado: lista de snapshots + las respuestas que cada prueba indique por "METODO /ruta". */
function mockApi(routes: Record<string, () => Response>) {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace(/^\/api/, '');
      const method = init?.method ?? 'GET';
      calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : null });
      if (path === '/market/snapshots') return new Response(JSON.stringify({ snapshots: SNAPSHOTS }));
      const snap = SNAPSHOTS.find((s) => path === `/market/snapshots/${s.id}`);
      if (snap) return new Response(
          JSON.stringify({
            ...snap,
            quotes: [],
            curves: {
              'TIIE-F': { currency: 'MXN', period_days: 28, points: [] },
              SOFR: { currency: 'USD', period_days: 365, points: [] },
            },
          }),
        );
      const route = routes[`${method} ${path}`];
      return route ? route() : new Response(JSON.stringify({ error: 'sin ruta', field: null }), { status: 404 });
    }),
  );
  return { calls, of: (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path) };
}

const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status });

/** Operación tal como la devuelve `POST /trades`. */
const tradeBody = (over: Record<string, unknown> = {}) => ({
  id: 7,
  product: 'irs',
  counterparty: 'Banorte',
  trade_date: '2026-11-10',
  start_date: '2026-11-10',
  maturity_date: '2027-11-03',
  params: {},
  notional: 1,
  currency: 'MXN',
  maturity: '2027-11-03',
  created_at: 'x',
  ...over,
});

const dateInput = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const add = () => fireEvent.click(screen.getByRole('button', { name: 'Agregar al portafolio' }));
/** Pacto e inicio se prellenan con el `as_of` del snapshot cuando llega la lista. */
const prefilled = (asOf = '2026-11-10') =>
  waitFor(() => {
    expect(dateInput('Fecha de pacto').value).toBe(asOf);
    expect(dateInput('Inicio').value).toBe(asOf);
  });

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderForm(product: keyof typeof PRODUCT_SPECS = 'irs') {
  return render(
    <SnapshotProvider>
      <MemoryRouter>
        <PricerForm spec={PRODUCT_SPECS[product]} />
        <SwitchTo id="ALT" />
      </MemoryRouter>
    </SnapshotProvider>,
  );
}

const valuate = () => fireEvent.click(screen.getByRole('button', { name: 'Valuar' }));

afterEach(() => {
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

describe('PricerForm', () => {
  it('muestra el error 400 junto al campo que lo causa y no como banner', async () => {
    mockApi({
      'POST /price/irs': json({ error: 'El nocional debe ser mayor que 0', field: 'notional' }, 400),
    });
    renderForm();

    fireEvent.change(screen.getByLabelText('Nocional'), { target: { value: '-5' } });
    valuate();

    const message = await screen.findByText('El nocional debe ser mayor que 0');
    const input = screen.getByLabelText('Nocional');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById(input.getAttribute('aria-describedby') ?? '')).toBe(message);
    expect(input.closest('.pricer__field')?.contains(message)).toBe(true);
    // el único aviso es el del campo; no hay banner general ni resultado
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.queryByText('Valor presente')).toBeNull();
  });

  it('un error sin campo asociado sale como banner', async () => {
    mockApi({ 'POST /price/irs': json({ error: 'No se pudo valuar: curva vacía', field: null }, 400) });
    renderForm();

    valuate();

    const banner = await screen.findByRole('alert');
    expect(banner.textContent).toBe('No se pudo valuar: curva vacía');
    expect(banner.closest('.pricer__field')).toBeNull();
  });

  it('envía los defaults con la tasa fija opcional omitida y el snapshot activo', async () => {
    const api = mockApi({ 'POST /price/irs': json(IRS_RESPONSE) });
    renderForm();

    valuate();

    await screen.findAllByText('MXN 1,234.50', { selector: '.pricer__pv' });
    expect(api.of('POST', '/price/irs')[0].body).toEqual({
      curve: 'TIIE-F',
      side: 'payer',
      notional: 100000000,
      periods: 13,
      snapshot: 'MX-DEMO',
    });
  });

  it('la tasa fija se captura en % y viaja en decimal', async () => {
    const api = mockApi({ 'POST /price/irs': json(IRS_RESPONSE) });
    renderForm();

    fireEvent.change(screen.getByLabelText('Tasa fija'), { target: { value: '7.1' } });
    valuate();

    await screen.findByText('Medidas de riesgo');
    expect(api.of('POST', '/price/irs')[0].body?.fixed_rate).toBe(0.071);
  });

  it('un valor no numérico se señala en el campo sin llamar al backend', async () => {
    const api = mockApi({});
    renderForm();

    fireEvent.change(screen.getByLabelText('Periodos'), { target: { value: 'doce' } });
    valuate();

    expect((await screen.findByRole('alert')).textContent).toBe('Debe ser un número');
    expect(api.of('POST', '/price/irs')).toHaveLength(0);
  });

  it('muestra PV, riesgo y gráfica de flujos tras valuar', async () => {
    mockApi({ 'POST /price/irs': json(IRS_RESPONSE) });
    renderForm();

    valuate();

    await screen.findByText('Medidas de riesgo');
    expect(screen.getByText('DV01')).toBeTruthy();
    expect(screen.getByText('-4,567.80')).toBeTruthy();
    expect(screen.getByText('6.7100 %')).toBeTruthy();
    expect(screen.getByTestId('chart').getAttribute('data-kind')).toBe('cashflows');
  });

  it('Agregar al portafolio llama a createTrade con producto, contraparte, parámetros y fechas', async () => {
    const api = mockApi({ 'POST /trades': json(tradeBody(), 201) });
    renderForm();
    await prefilled();

    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: ' Banorte ' } });
    add();

    await screen.findByText(/Operación 7 agregada/);
    expect(api.of('POST', '/trades')[0].body).toEqual({
      product: 'irs',
      counterparty: 'Banorte',
      params: { curve: 'TIIE-F', side: 'payer', notional: 100000000, periods: 13 },
      trade_date: '2026-11-10',
      start_date: '2026-11-10',
    });
  });

  it('tras valuar un irs con la tasa en blanco la rellena con la usada y "Agregar" la envía', async () => {
    const api = mockApi({
      'POST /price/irs': json({ ...IRS_RESPONSE, details: { fixed_rate: 0.0671234567 } }),
      'POST /trades': json(tradeBody({ id: 8 }), 201),
    });
    renderForm();
    expect((screen.getByLabelText('Tasa fija') as HTMLInputElement).value).toBe('');

    valuate();

    await waitFor(() => expect((screen.getByLabelText('Tasa fija') as HTMLInputElement).value).toBe('6.71234567'));
    // la valuación salió sin tasa (par); la operación guardada lleva la tasa explícita
    expect(api.of('POST', '/price/irs')[0].body).not.toHaveProperty('fixed_rate');
    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: 'Banorte' } });
    fireEvent.click(screen.getByRole('button', { name: 'Agregar al portafolio' }));

    await screen.findByText(/Operación 8 agregada/);
    expect(api.of('POST', '/trades')[0].body?.params).toEqual({
      curve: 'TIIE-F',
      side: 'payer',
      notional: 100000000,
      periods: 13,
      fixed_rate: 0.0671234567,
    });
  });

  it('con una tasa fija capturada no se sobrescribe tras valuar', async () => {
    mockApi({ 'POST /price/irs': json({ ...IRS_RESPONSE, details: { fixed_rate: 0.071 } }) });
    renderForm();

    fireEvent.change(screen.getByLabelText('Tasa fija'), { target: { value: '7.1' } });
    valuate();

    await screen.findByText('Medidas de riesgo');
    expect((screen.getByLabelText('Tasa fija') as HTMLInputElement).value).toBe('7.1');
  });

  it('las fechas de pacto, inicio y vencimiento viajan en la petición', async () => {
    const api = mockApi({ 'POST /trades': json(tradeBody({ maturity_date: '2027-05-10' }), 201) });
    renderForm();
    await prefilled();

    fireEvent.change(dateInput('Fecha de pacto'), { target: { value: '2026-11-05' } });
    fireEvent.change(dateInput('Inicio'), { target: { value: '2026-11-12' } });
    fireEvent.change(dateInput('Vencimiento'), { target: { value: '2027-05-10' } });
    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: 'Banorte' } });
    add();

    await screen.findByText(/Operación 7 agregada/);
    expect(api.of('POST', '/trades')[0].body).toMatchObject({
      trade_date: '2026-11-05',
      start_date: '2026-11-12',
      maturity_date: '2027-05-10',
    });
  });

  it('sin vencimiento no se envía la clave maturity_date', async () => {
    const api = mockApi({ 'POST /trades': json(tradeBody(), 201) });
    renderForm();
    await prefilled();
    expect(dateInput('Vencimiento').value).toBe('');
    expect(screen.getByText('Vacío: se calcula con el plazo')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: 'Banorte' } });
    add();

    await screen.findByText(/Operación 7 agregada/);
    expect(api.of('POST', '/trades')[0].body).not.toHaveProperty('maturity_date');
  });

  it('pacto e inicio siguen al snapshot activo salvo que se hayan editado', async () => {
    mockApi({});
    renderForm();
    await prefilled('2026-11-10');

    fireEvent.change(dateInput('Inicio'), { target: { value: '2026-12-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'cambiar a ALT' }));

    await waitFor(() => expect(dateInput('Fecha de pacto').value).toBe('2026-11-11'));
    expect(dateInput('Inicio').value).toBe('2026-12-01');
  });

  it('el error 400 de maturity_date aparece bajo Vencimiento', async () => {
    mockApi({
      'POST /trades': json({ error: 'El vencimiento debe ser posterior al inicio', field: 'maturity_date' }, 400),
    });
    renderForm();
    await prefilled();

    fireEvent.change(dateInput('Vencimiento'), { target: { value: '2026-01-01' } });
    add();

    const message = await screen.findByText('El vencimiento debe ser posterior al inicio');
    const input = dateInput('Vencimiento');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe(message.id);
    expect(input.closest('.pricer__field')?.contains(message)).toBe(true);
    // el único aviso es el del campo: no hay banner general
    expect(screen.getAllByRole('alert')).toHaveLength(1);
  });

  it('el error 400 de start_date aparece bajo Inicio y se limpia al editarlo', async () => {
    mockApi({ 'POST /trades': json({ error: 'El inicio no puede ser anterior al pacto', field: 'start_date' }, 400) });
    renderForm();
    await prefilled();

    add();

    const message = await screen.findByText('El inicio no puede ser anterior al pacto');
    expect(dateInput('Inicio').closest('.pricer__field')?.contains(message)).toBe(true);
    fireEvent.change(dateInput('Inicio'), { target: { value: '2026-11-11' } });
    expect(screen.queryByText('El inicio no puede ser anterior al pacto')).toBeNull();
  });

  it('tras crear muestra el vencimiento devuelto y enlaza a la ficha', async () => {
    mockApi({ 'POST /trades': json(tradeBody({ id: 9, maturity_date: '2027-11-03' }), 201) });
    renderForm();
    await prefilled();

    add();

    await screen.findByText(/Operación 9 agregada/);
    expect(screen.getByText(/^Vencimiento:/).textContent).toBe('Vencimiento: 2027-11-03');
    expect(screen.queryByText(/Vencimiento ajustado/)).toBeNull();
    expect(screen.getByRole('link', { name: 'Ver ficha' }).getAttribute('href')).toBe('/portafolio/9');
  });

  it('si el vencimiento devuelto difiere del capturado se rotula como ajustado', async () => {
    mockApi({ 'POST /trades': json(tradeBody({ maturity_date: '2027-11-03' }), 201) });
    renderForm();
    await prefilled();

    fireEvent.change(dateInput('Vencimiento'), { target: { value: '2027-11-10' } });
    add();

    await screen.findByText(/Operación 7 agregada/);
    expect(screen.getByText(/^Vencimiento ajustado:/).textContent).toBe('Vencimiento ajustado: 2027-11-03');
  });

  it('el error de contraparte vacía aparece junto a su input', async () => {
    mockApi({
      'POST /trades': json({ error: 'La contraparte es obligatoria', field: 'counterparty' }, 400),
    });
    renderForm();

    fireEvent.click(screen.getByRole('button', { name: 'Agregar al portafolio' }));

    const message = await screen.findByText('La contraparte es obligatoria');
    expect(screen.getByLabelText('Contraparte').getAttribute('aria-describedby')).toBe(message.id);
  });

  it('revalúa al cambiar de snapshot si ya hay resultado', async () => {
    const api = mockApi({ 'POST /price/irs': json(IRS_RESPONSE) });
    renderForm();
    valuate();
    await screen.findByText('Medidas de riesgo');
    expect(api.of('POST', '/price/irs')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: 'cambiar a ALT' }));

    await waitFor(() => expect(api.of('POST', '/price/irs')).toHaveLength(2));
    expect(api.of('POST', '/price/irs')[1].body?.snapshot).toBe('ALT');
  });

  it('no valúa por sí solo al cambiar de snapshot si no hay resultado', async () => {
    const api = mockApi({});
    renderForm();
    await screen.findByRole('button', { name: 'cambiar a ALT' });

    fireEvent.click(screen.getByRole('button', { name: 'cambiar a ALT' }));
    await waitFor(() => expect(api.of('GET', '/market/snapshots/ALT')).toHaveLength(1));

    expect(api.of('POST', '/price/irs')).toHaveLength(0);
  });

  it('forward FX: valida con los campos de su especificación', async () => {
    const api = mockApi({
      'POST /price/fx_forward': json({
        product: 'fx_forward',
        currency: 'MXN',
        pv: 5000,
        pv_mxn: 5000,
        risk: { delta: 1e6, forward: 18.9 },
        cashflows: null,
        details: {},
      }),
    });
    renderForm('fx_forward');

    valuate();

    await screen.findByText('Medidas de riesgo');
    expect(api.of('POST', '/price/fx_forward')[0].body).toEqual({
      side: 'buy',
      notional_usd: 1000000,
      strike: 18.9,
      days: 91,
      snapshot: 'MX-DEMO',
    });
  });

  it('cross currency swap: el resultado trae diferencial par en pb, nocional, tipo de cambio, DV01 por curva y curva de descuento', async () => {
    mockApi({ 'POST /price/xccy_swap': json(XCCY_RESPONSE) });
    renderForm('xccy_swap');

    valuate();

    await screen.findByText('Medidas de riesgo');
    const rowOf = (label: string) => screen.getByText(label).closest('tr') as HTMLElement;
    expect(within(rowOf('Diferencial par')).getByText('-10.00 pb')).toBeTruthy();
    expect(within(rowOf('DV01 MXN-USD')).getByText('1,234.50')).toBeTruthy();
    expect(within(rowOf('DV01 TIIE-F')).getByText('-50.10')).toBeTruthy();
    expect(within(rowOf('DV01 SOFR')).getByText('980.20')).toBeTruthy();
    expect(within(rowOf('Nocional MXN')).getByText('MXN 186,000,000.00')).toBeTruthy();
    expect(within(rowOf('Tipo de cambio')).getByText('18.6000')).toBeTruthy();
    expect(screen.getByText('Curva de descuento: MXN-USD')).toBeTruthy();
    expect(screen.queryByText(NO_CSA_TEXT)).toBeNull();
    // PV en MXN
    expect(screen.getAllByText('MXN 12,345.60').length).toBeGreaterThan(0);
  });

  it('cross currency swap sin curva MXN-USD (descuento TIIE-F) muestra el texto de sin curva', async () => {
    mockApi({
      'POST /price/xccy_swap': json({ ...XCCY_RESPONSE, details: { ...XCCY_RESPONSE.details, discount_curve: 'TIIE-F' } }),
    });
    renderForm('xccy_swap');

    valuate();

    expect(await screen.findByText(NO_CSA_TEXT)).toBeTruthy();
    expect(screen.queryByText('Curva de descuento: MXN-USD')).toBeNull();
  });

  it('cross currency swap: la tabla de flujos lleva Pata y Tipo, y la gráfica es por pata', async () => {
    grids.options.length = 0;
    mockApi({ 'POST /price/xccy_swap': json(XCCY_RESPONSE) });
    renderForm('xccy_swap');

    valuate();

    const heading = await screen.findByRole('heading', { name: 'VP de los flujos por pata (MXN)' });
    expect(within(heading.closest('section') as HTMLElement).getByTestId('chart').getAttribute('data-kind')).toBe('cashflows');
    const cols = grids.options[grids.options.length - 1].columnDefs;
    expect(cols.map((c) => c.headerName)).toEqual(['Fecha', 'Pata', 'Tipo', 'Monto', 'Factor desc.', 'VP (MXN)']);
    expect(cols[1].valueFormatter?.({ value: 'MXN' })).toBe(LEG_LABEL.MXN);
    expect(cols[2].valueFormatter?.({ value: 'exchange' })).toBe('Intercambio de nocional');
    expect(cols[2].valueFormatter?.({ value: 'coupon' })).toBe('Cupón');
  });

  it('los demás productos conservan su tabla y su gráfica de flujos sin Pata', async () => {
    grids.options.length = 0;
    mockApi({ 'POST /price/irs': json(IRS_RESPONSE) });
    renderForm();

    valuate();

    await screen.findByText('Medidas de riesgo');
    expect(screen.getByRole('heading', { name: 'Perfil de flujos' })).toBeTruthy();
    expect(grids.options[grids.options.length - 1].columnDefs.map((c) => c.headerName)).toEqual([
      'Fecha',
      'Días',
      'Monto',
      'Factor desc.',
      'VP',
    ]);
    expect(screen.queryByText('Detalle del swap')).toBeNull();
  });

  it('cross currency swap: valúa con los campos de su especificación y se agrega como los demás productos', async () => {
    const api = mockApi({
      'POST /price/xccy_swap': json(XCCY_RESPONSE),
      'POST /trades': json(tradeBody({ id: 9, product: 'xccy_swap', maturity_date: '2027-11-03' }), 201),
    });
    renderForm('xccy_swap');
    await prefilled();

    valuate();
    await screen.findByText('Medidas de riesgo');
    expect(api.of('POST', '/price/xccy_swap')[0].body).toEqual({
      side: 'pay_usd',
      notional_usd: 10000000,
      periods: 26,
      exchange: 'both',
      snapshot: 'MX-DEMO',
    });

    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: 'Banorte' } });
    add();

    await screen.findByText(/Operación 9 agregada/);
    expect(api.of('POST', '/trades')[0].body).toEqual({
      product: 'xccy_swap',
      counterparty: 'Banorte',
      // como en el irs, el diferencial en blanco se rellena con el que usó el backend (el par)
      params: { side: 'pay_usd', notional_usd: 10000000, periods: 26, exchange: 'both', spread: -0.001 },
      trade_date: '2026-11-10',
      start_date: '2026-11-10',
    });
  });

  it.each([
    ['cap_floor', 'Pago por periodo contra la tasa de referencia', '28'],
    ['swaption', 'Valor intrínseco al vencimiento contra la tasa swap', '28'],
    ['fx_forward', 'Resultado al vencimiento del forward', null],
  ] as const)('%s: tras valuar monta la tarjeta de gráfica de payoff', async (product, title, periodDays) => {
    mockApi({
      [`POST /price/${product}`]: json({
        product,
        currency: 'MXN',
        pv: 5000,
        pv_mxn: 5000,
        risk: {},
        cashflows: null,
        details: {},
      }),
    });
    renderForm(product);

    valuate();

    const heading = await screen.findByRole('heading', { name: title });
    const card = heading.closest('section') as HTMLElement;
    const chart = within(card).getByTestId('chart');
    expect(chart.getAttribute('data-kind')).toBe('payoff');
    expect(chart.getAttribute('data-product')).toBe(product);
    // el periodo de pago sale de la curva del snapshot, que llega aparte de la valuación
    await waitFor(() => expect(chart.getAttribute('data-period-days')).toBe(periodDays));
    // solo la swaption avisa que su gráfica es aproximada
    const note = 'Aproximación con descuento plano; el PV exacto es el de arriba.';
    expect(within(card).queryByText(note) !== null).toBe(product === 'swaption');
  });
});

describe('exóticos de FX', () => {
  /** Como lo entrega `POST /api/price/fx_*`: la serie de la gráfica viene del backend, con una marca por barrera. */
  const exotic = (product: string, barriers: number[], over: Record<string, unknown> = {}): PriceResponse => ({
    product: product as PriceResponse['product'],
    currency: 'MXN',
    pv: 412345.678,
    pv_mxn: 412345.678,
    risk: { delta: -52000, vega: -8100 },
    cashflows: null,
    details: {
      price_pct: 41.23,
      no_touch_probability: 0.4175,
      std_error: 1234.5678,
      paths: 20000,
      model: 'smile',
      method: 'mc',
      analytic_flat_pv: 400000,
      chart: { strike: null, barriers, spots: [18.5, 19, 19.4], pnl: [1, 2, 3] },
      ...over,
    },
  });

  it('no touch: envía los valores por omisión y dibuja la serie del backend tal cual, sin recalcularla', async () => {
    const api = mockApi({ 'POST /price/fx_no_touch': json(exotic('fx_no_touch', [19.5])) });
    renderForm('fx_no_touch');

    valuate();

    const heading = await screen.findByRole('heading', { name: 'Valor contra spot' });
    expect(api.of('POST', '/price/fx_no_touch')[0].body).toEqual({
      side: 'buy',
      barrier: 19.5,
      barrier_type: 'up',
      payout_mxn: 1000000,
      days: 91,
      model: 'smile',
      method: 'mc',
      snapshot: 'MX-DEMO',
    });
    const chart = within(heading.closest('section') as HTMLElement).getByTestId('chart');
    expect(chart.getAttribute('data-product')).toBe('fx_no_touch');
    expect(JSON.parse(chart.getAttribute('data-series') as string)).toEqual({
      strike: null,
      barriers: [19.5],
      spots: [18.5, 19, 19.4],
      pnl: [1, 2, 3],
    });
  });

  it('double no touch: manda las dos barreras y la serie lleva las dos marcas', async () => {
    const api = mockApi({ 'POST /price/fx_double_no_touch': json(exotic('fx_double_no_touch', [17.5, 19.8])) });
    renderForm('fx_double_no_touch');

    valuate();

    const chart = await screen.findByTestId('chart');
    expect(api.of('POST', '/price/fx_double_no_touch')[0].body).toMatchObject({ lower: 17.5, upper: 19.8 });
    expect(JSON.parse(chart.getAttribute('data-series') as string).barriers).toEqual([17.5, 19.8]);
  });

  it('muestra el error estándar junto al PV y los datos del cálculo con sus rótulos', async () => {
    mockApi({ 'POST /price/fx_no_touch': json(exotic('fx_no_touch', [19.5])) });
    renderForm('fx_no_touch');

    valuate();

    await screen.findByText('± MXN 1,234.57 (error estándar)');
    const block = screen.getByText('Detalle del cálculo').closest('section') as HTMLElement;
    const row = (label: string) => (within(block).getByText(label).closest('tr') as HTMLElement).textContent;
    expect(row('Probabilidad de no tocar')).toContain('41.75 %');
    expect(row('Precio (% del pago)')).toContain('41.23 %');
    expect(row('Referencia analítica (plano)')).toContain('MXN 400,000.00');
    expect(row('Trayectorias')).toContain('20,000');
    expect(row('Modelo')).toContain('Con sonrisa (vol local)');
    expect(row('Método')).toContain('Monte Carlo');
  });

  it('con método analítico (error estándar 0) no muestra el error estándar', async () => {
    mockApi({
      'POST /price/fx_no_touch': json(exotic('fx_no_touch', [19.5], { std_error: 0, paths: 0, method: 'analytic' })),
    });
    renderForm('fx_no_touch');

    valuate();

    await screen.findByText('Medidas de riesgo');
    expect(screen.queryByText(/error estándar/)).toBeNull();
    const block = screen.getByText('Detalle del cálculo').closest('section') as HTMLElement;
    expect(within(block).getByText('Analítico')).toBeTruthy();
  });

  it('sin referencia analítica (la serie no converge con corredores muy anchos) muestra «—» en vez de cero', async () => {
    mockApi({
      'POST /price/fx_double_no_touch': json(exotic('fx_double_no_touch', [0.01, 1000000], { analytic_flat_pv: null })),
    });
    renderForm('fx_double_no_touch');

    valuate();

    const block = (await screen.findByText('Detalle del cálculo')).closest('section') as HTMLElement;
    const row = (label: string) => (within(block).getByText(label).closest('tr') as HTMLElement).textContent;
    expect(row('Referencia analítica (plano)')).toBe('Referencia analítica (plano)—');
    expect(row('Trayectorias')).toContain('20,000');
  });

  it.each(['fx_no_touch', 'fx_double_no_touch'] as const)('%s no ofrece agregar al portafolio', (product) => {
    renderForm(product);
    expect(screen.queryByRole('button', { name: 'Agregar al portafolio' })).toBeNull();
    expect(screen.queryByLabelText('Contraparte')).toBeNull();
  });

  it('los demás productos siguen sin error estándar ni datos del cálculo', async () => {
    mockApi({ 'POST /price/irs': json(IRS_RESPONSE) });
    renderForm('irs');

    valuate();

    await screen.findByText('Medidas de riesgo');
    expect(screen.queryByText('Detalle del cálculo')).toBeNull();
    expect(screen.queryByText(/error estándar/)).toBeNull();
    expect(screen.getByRole('button', { name: 'Agregar al portafolio' })).toBeTruthy();
  });
});

describe('cashflowsByLeg', () => {
  it('una serie por pata sobre las fechas de pago, con el VP en MXN y sumando cupón e intercambio de un mismo día', () => {
    const byLeg = cashflowsByLeg(XCCY_FLOWS)!;
    expect(byLeg.dates).toEqual(['2026-12-08', '2027-01-05']);
    expect(byLeg.legs.map((l) => l.leg)).toEqual(['USD', 'MXN']);
    expect(byLeg.legs[0].values).toEqual([-562464, -554652 + 184884000]);
    expect(byLeg.legs[1].values).toEqual([1003955, -184140000]);
  });

  it('una fecha donde una pata no paga queda en blanco y una sola pata da una sola serie', () => {
    const byLeg = cashflowsByLeg(XCCY_FLOWS.filter((f) => f.leg === 'USD' || f.date === '2026-12-08'))!;
    expect(byLeg.legs.map((l) => l.leg)).toEqual(['USD', 'MXN']);
    expect(byLeg.legs[1].values).toEqual([1003955, null]);
    expect(cashflowsByLeg(XCCY_FLOWS.filter((f) => f.leg === 'MXN'))!.legs.map((l) => l.leg)).toEqual(['MXN']);
  });

  it('sin flujos con pata (los demás productos) no hay series por pata', () => {
    expect(cashflowsByLeg(IRS_RESPONSE.cashflows!)).toBeNull();
    expect(cashflowsByLeg([])).toBeNull();
  });
});
