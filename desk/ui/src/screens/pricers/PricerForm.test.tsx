import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PriceResponse } from '../../api/types';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { PricerForm } from './PricerForm';
import { PRODUCT_SPECS } from './registry';

// echarts y AG Grid dependen de medidas de layout que jsdom no tiene; aquí solo importa
// qué datos reciben, no cómo pintan.
vi.mock('./PricerChart', () => ({
  PricerChart: ({ data }: { data: { kind: string } }) => <div data-testid="chart" data-kind={data.kind} />,
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
      if (snap) return new Response(JSON.stringify({ ...snap, quotes: [], curves: {} }));
      const route = routes[`${method} ${path}`];
      return route ? route() : new Response(JSON.stringify({ error: 'sin ruta', field: null }), { status: 404 });
    }),
  );
  return { calls, of: (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path) };
}

const json = (body: unknown, status = 200) => () => new Response(JSON.stringify(body), { status });

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

  it('Agregar al portafolio llama a createTrade con {product, counterparty, params}', async () => {
    const api = mockApi({
      'POST /trades': json(
        { id: 7, product: 'irs', counterparty: 'Banorte', params: {}, notional: 1, currency: 'MXN', maturity: '2027-11-10', created_at: 'x' },
        201,
      ),
    });
    renderForm();

    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: ' Banorte ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Agregar al portafolio' }));

    await screen.findByText(/Operación 7 agregada/);
    expect(api.of('POST', '/trades')[0].body).toEqual({
      product: 'irs',
      counterparty: 'Banorte',
      params: { curve: 'TIIE-F', side: 'payer', notional: 100000000, periods: 13 },
    });
  });

  it('tras valuar un irs con la tasa en blanco la rellena con la usada y "Agregar" la envía', async () => {
    const api = mockApi({
      'POST /price/irs': json({ ...IRS_RESPONSE, details: { fixed_rate: 0.0671234567 } }),
      'POST /trades': json(
        { id: 8, product: 'irs', counterparty: 'Banorte', params: {}, notional: 1, currency: 'MXN', maturity: '2027-11-10', created_at: 'x' },
        201,
      ),
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
    expect(screen.queryByTestId('chart')).toBeNull();
  });
});
