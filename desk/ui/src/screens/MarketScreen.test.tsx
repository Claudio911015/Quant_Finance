import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Snapshot, Source } from '../api/types';
import { SnapshotProvider, useSnapshot } from '../state/SnapshotContext';
import { MarketScreen } from './MarketScreen';

// echarts pinta en canvas, que jsdom no tiene; aquí solo importa qué opción recibe cada gráfica.
const charts: { option: { series?: { name?: string; type: string; data: unknown[] }[] }; ariaLabel?: string }[] = [];
vi.mock('../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: (typeof charts)[number]) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

// Las fijaciones tienen su propia prueba (FixingsPanel.test.tsx) y piden /api/fixings, que los mocks de aquí no atienden.
vi.mock('./FixingsPanel', () => ({ default: () => null }));

function point(label: string, days: number, zero: number, forward: number) {
  return { label, days, t: days / 365, zero, df: 1 - zero * (days / 365), forward };
}

const SYNTHETIC: Source = { kind: 'synthetic', label: 'Sintético', as_of: null };

const SNAPSHOT: Snapshot = {
  id: 'MX-DEMO',
  label: 'México demo (sintético)',
  synthetic: true,
  as_of: '2026-11-10',
  data_quality: 'synthetic',
  read_only: false,
  sources: {
    'curve:TIIE-F': SYNTHETIC,
    'curve:SOFR': SYNTHETIC,
    spot: SYNTHETIC,
    surface: SYNTHETIC,
    hw: SYNTHETIC,
    factor_vols: SYNTHETIC,
    factor_corr: SYNTHETIC,
  },
  quotes: [
    { id: 'TIIE-F:13x28', curve: 'TIIE-F', label: '13x28', type: 'ois', days: 364, rate: 0.0675 },
    { id: 'SOFR:1Y', curve: 'SOFR', label: '1Y', type: 'ois', days: 365, rate: 0.04 },
  ],
  curves: {
    'TIIE-F': {
      currency: 'MXN',
      period_days: 28,
      points: [point('13x28', 364, 0.0661, 0.0661)],
    },
    SOFR: { currency: 'USD', period_days: 365, points: [point('1Y', 365, 0.0395, 0.0395)] },
  },
  fx: { pair: 'USDMXN', spot: 18.6 },
  vol_surface: {
    pair: 'USDMXN',
    expiry_days: [30, 91],
    strikes: [17, 18.6],
    vols: [
      [0.12, 0.11],
      [0.13, 0.12],
    ],
  },
  hw: { 'TIIE-F': { a: 0.05, sigma: 0.01 }, SOFR: { a: 0.03, sigma: 0.008 } },
  factors: { names: [], units: [], daily_vols: [], correlations: [] },
};

const LIVE: Snapshot = {
  ...SNAPSHOT,
  id: 'MKT-LIVE',
  label: 'Mercado vivo (SOFR aproximada)',
  as_of: '2026-11-10',
  data_quality: 'mixed',
  read_only: true,
  sources: {
    'curve:TIIE-F': { kind: 'synthetic', label: 'Sintética: sin datos libres (Banxico exige token)', as_of: null },
    'curve:SOFR': { kind: 'proxy', label: 'Aproximada: 1D = SOFR overnight (FRBNY)', as_of: '2026-11-10' },
    spot: { kind: 'live', label: 'FRED DEXMXUS (mediodía de Nueva York)', as_of: '2026-11-06' },
    surface: { kind: 'synthetic', label: 'Sintética: sin datos libres de volatilidad USDMXN', as_of: null },
    hw: { kind: 'synthetic', label: 'Sintéticos (heredados de MX-DEMO)', as_of: null },
    factor_vols: { kind: 'mixed', label: 'SOFR y USDMXN medidas; TIIE-F sintética', as_of: '2026-11-10' },
    factor_corr: { kind: 'synthetic', label: 'Sintéticas (heredadas de MX-DEMO)', as_of: null },
  },
  fx: { pair: 'USDMXN', spot: 18.6226 },
};

const REFRESH_OK = {
  ran_at: '2026-11-11T15:04:05+00:00',
  mdf_exit_code: 0,
  treasury_latest: '2026-11-10',
  sofr_latest: '2026-11-09',
  fred_latest: '2026-11-06',
  snapshot: LIVE,
};

const READ_ONLY_NOTE = 'Mercado vivo se reconstruye en cada actualización; sus cotizaciones y el spot no se editan.';

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

/**
 * Backend con estado: `ids` es lo que lista el servidor (en el orden de la API, MKT-LIVE primero)
 * y `refresh` responde al POST; el refresco real crea MKT-LIVE, así que el mock lo agrega a la lista.
 */
function mockBackend(opts: { live: boolean; refresh?: () => Response | Promise<Response> }) {
  let hasLive = opts.live;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(/^\/api/, '');
    if (init?.method === 'POST' && path === '/market/refresh') {
      const res = await (opts.refresh ?? (() => json(REFRESH_OK)))();
      if (res.status === 200) hasLive = true;
      return res;
    }
    if (path === '/market/snapshots') {
      return json({ snapshots: hasLive ? [LIVE, SNAPSHOT] : [SNAPSHOT] });
    }
    if (path === '/market/snapshots/MKT-LIVE' && hasLive) return json(LIVE);
    if (path === '/market/snapshots/MX-DEMO') return json(SNAPSHOT);
    return json({ error: 'Snapshot no encontrado', field: null }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const gets = (fetchMock: ReturnType<typeof mockBackend>, path: string) =>
  fetchMock.mock.calls.filter(([url, init]) => url === `/api${path}` && init?.method === 'GET').length;

const posts = (fetchMock: ReturnType<typeof mockBackend>) =>
  fetchMock.mock.calls.filter(([url, init]) => url === '/api/market/refresh' && init?.method === 'POST');

/** Botón para fijar MX-DEMO como activo aunque MKT-LIVE esté en la lista (elección explícita). */
function PickDemo() {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId('MX-DEMO')}>elegir MX-DEMO</button>;
}

function mockApi(onPut?: (body: unknown) => Response) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(/^\/api/, '');
    if (init?.method === 'PUT' && onPut) return onPut(JSON.parse(String(init.body)));
    if (path === '/market/snapshots') {
      return new Response(JSON.stringify({ snapshots: [SNAPSHOT] }), { status: 200 });
    }
    return new Response(JSON.stringify(SNAPSHOT), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const puts = (fetchMock: ReturnType<typeof mockApi>) =>
  fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT');

const rateCells = (container: HTMLElement) =>
  Array.from(container.querySelectorAll<HTMLElement>('.ag-cell[col-id="ratePct"]'));

/** Abre el editor de la primera tasa (TIIE-F), escribe `pct` y confirma con Enter. */
async function editFirstRate(container: HTMLElement, pct: string) {
  await waitFor(() => expect(rateCells(container)).toHaveLength(2));
  const cell = rateCells(container)[0];
  fireEvent.doubleClick(cell);
  cell.focus();
  fireEvent.keyDown(cell, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13 });
  const input = await waitFor(() => {
    const el = cell.querySelector('input');
    expect(el).toBeTruthy();
    return el as HTMLInputElement;
  });
  input.value = pct;
  fireEvent.input(input);
  input.focus();
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13 });
}

function renderScreen() {
  return render(
    <SnapshotProvider>
      <MarketScreen />
    </SnapshotProvider>,
  );
}

beforeEach(() => {
  charts.length = 0;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('MarketScreen', () => {
  it('muestra los parámetros Hull-White como texto, sin inputs', async () => {
    mockApi();
    renderScreen();

    const table = await screen.findByRole('table', { name: 'Parámetros Hull-White' });
    expect(within(table).getByText('0.0500')).toBeTruthy();
    expect(within(table).getByText('0.0100')).toBeTruthy();
    expect(within(table).getByText('0.0300')).toBeTruthy();
    expect(within(table).getByText('0.0080')).toBeTruthy();
    expect(table.querySelector('input, select, textarea')).toBeNull();
  });

  it('dibuja cero y forward de cada curva en %', async () => {
    mockApi();
    renderScreen();

    await screen.findByRole('img', { name: 'Curva TIIE-F: cero y forward' });
    const tiie = charts.find((c) => c.ariaLabel === 'Curva TIIE-F: cero y forward')!;
    expect(tiie.option.series!.map((s) => s.name)).toEqual(['Cero', 'Forward']);
    expect(tiie.option.series![0].data).toEqual([[364, 6.61]]);
    expect(screen.getByRole('img', { name: 'Curva SOFR: cero y forward' })).toBeTruthy();
    expect(screen.getByRole('img', { name: /superficie de volatilidad/ })).toBeTruthy();
  });

  it('editar el spot llama a updateSnapshot con {spot} y muestra la respuesta', async () => {
    const updated = { ...SNAPSHOT, fx: { pair: 'USDMXN', spot: 18.75 } };
    const fetchMock = mockApi(() => new Response(JSON.stringify(updated), { status: 200 }));
    renderScreen();

    const input = (await screen.findByLabelText('Spot USDMXN')) as HTMLInputElement;
    expect(input.value).toBe('18.6');
    fireEvent.change(input, { target: { value: '18.75' } });
    fireEvent.blur(input);

    await waitFor(() => expect(puts(fetchMock)).toHaveLength(1));
    const [url, init] = puts(fetchMock)[0];
    expect(url).toBe('/api/market/snapshots/MX-DEMO');
    expect(JSON.parse(String(init!.body))).toEqual({ spot: 18.75 });
    await waitFor(() => expect((screen.getByLabelText('Spot USDMXN') as HTMLInputElement).value).toBe('18.75'));
  });

  it('si el backend rechaza el spot, muestra el error y restaura el valor', async () => {
    const fetchMock = mockApi(
      () => new Response(JSON.stringify({ error: 'spot debe ser mayor que 0', field: 'spot' }), { status: 400 }),
    );
    renderScreen();

    const input = (await screen.findByLabelText('Spot USDMXN')) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '-1' } });
    fireEvent.blur(input);

    expect((await screen.findByRole('alert')).textContent).toBe('spot debe ser mayor que 0');
    expect(puts(fetchMock)).toHaveLength(1);
    expect((screen.getByLabelText('Spot USDMXN') as HTMLInputElement).value).toBe('18.6');
  });

  it('un spot no numérico no llega al backend', async () => {
    const fetchMock = mockApi();
    renderScreen();

    const input = (await screen.findByLabelText('Spot USDMXN')) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.blur(input);

    expect((await screen.findByRole('alert')).textContent).toBe('El spot debe ser un número');
    expect(puts(fetchMock)).toHaveLength(0);
    expect(input.value).toBe('18.6');
  });

  it('editar una tasa en % envía el decimal y redibuja la gráfica con la respuesta', async () => {
    const updated: Snapshot = {
      ...SNAPSHOT,
      quotes: [{ ...SNAPSHOT.quotes[0], rate: 0.0685 }, SNAPSHOT.quotes[1]],
      curves: {
        ...SNAPSHOT.curves,
        'TIIE-F': { currency: 'MXN', period_days: 28, points: [point('13x28', 364, 0.067, 0.067)] },
      },
    };
    const fetchMock = mockApi(() => new Response(JSON.stringify(updated), { status: 200 }));
    const { container } = renderScreen();

    await editFirstRate(container, '6.85');

    await waitFor(() => expect(puts(fetchMock)).toHaveLength(1));
    const [url, init] = puts(fetchMock)[0];
    expect(url).toBe('/api/market/snapshots/MX-DEMO');
    expect(JSON.parse(String(init!.body))).toEqual({ quotes: [{ id: 'TIIE-F:13x28', rate: 0.0685 }] });

    await waitFor(() => {
      const last = charts.filter((c) => c.ariaLabel === 'Curva TIIE-F: cero y forward').at(-1)!;
      expect((last.option.series![0].data[0] as number[])[1]).toBeCloseTo(6.7, 10);
    });
    expect(rateCells(container)[0].textContent).toBe('6.8500');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('si el backend rechaza la tasa, muestra el error junto a la tabla y revierte la celda', async () => {
    const fetchMock = mockApi(
      () =>
        new Response(JSON.stringify({ error: 'Tasa fuera de rango', field: 'quotes' }), { status: 400 }),
    );
    const { container } = renderScreen();

    await editFirstRate(container, '250');

    expect((await screen.findByRole('alert')).textContent).toBe('Tasa fuera de rango');
    expect(puts(fetchMock)).toHaveLength(1);
    await waitFor(() => expect(rateCells(container)[0].textContent).toBe('6.7500'));
  });

  it('cada curva, el spot y la superficie llevan su etiqueta: tipo, rótulo y fecha', async () => {
    mockBackend({ live: true });
    renderScreen();

    const tiie = await screen.findByRole('region', { name: 'TIIE-F' });
    expect(within(tiie).getByText('Sintética')).toBeTruthy();
    expect(within(tiie).getByText('Sintética: sin datos libres (Banxico exige token)')).toBeTruthy();
    expect(within(tiie).getByText('sin fecha')).toBeTruthy();

    const sofr = screen.getByRole('region', { name: 'SOFR' });
    expect(within(sofr).getByText('Aproximada')).toBeTruthy();
    expect(within(sofr).getByText('Aproximada: 1D = SOFR overnight (FRBNY)')).toBeTruthy();
    expect(within(sofr).getByText('2026-11-10')).toBeTruthy();

    const spot = screen.getByLabelText('Spot USDMXN').closest('.market__spot') as HTMLElement;
    expect(within(spot).getByText('En vivo')).toBeTruthy();
    expect(within(spot).getByText('FRED DEXMXUS (mediodía de Nueva York)')).toBeTruthy();
    expect(within(spot).getByText('2026-11-06')).toBeTruthy();

    const surface = screen.getByRole('region', { name: /Superficie de volatilidad/ });
    expect(within(surface).getByText('Sintética')).toBeTruthy();
    expect(within(surface).getByText('Sintética: sin datos libres de volatilidad USDMXN')).toBeTruthy();
    expect(within(surface).getByText('sin fecha')).toBeTruthy();
  });

  it('con read_only el spot y las tasas no se editan, no hay PUT y la nota lo explica', async () => {
    const fetchMock = mockBackend({ live: true });
    const { container } = renderScreen();

    expect((await screen.findByRole('note')).textContent).toBe(READ_ONLY_NOTE);
    expect((screen.getByLabelText('Spot USDMXN') as HTMLInputElement).disabled).toBe(true);

    await waitFor(() => expect(rateCells(container)).toHaveLength(2));
    const cell = rateCells(container)[0];
    fireEvent.doubleClick(cell);
    cell.focus();
    fireEvent.keyDown(cell, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13 });
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(cell.querySelector('input')).toBeNull();
    expect(cell.textContent).toBe('6.7500');
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
  });

  it('sin read_only no hay nota y el spot está habilitado', async () => {
    mockApi();
    renderScreen();

    const input = (await screen.findByLabelText('Spot USDMXN')) as HTMLInputElement;
    expect(input.disabled).toBe(false);
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('"Actualizar datos" hace POST, se deshabilita mientras corre, muestra las fechas y recarga lista y snapshot', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const fetchMock = mockBackend({
      live: true,
      refresh: async () => {
        await gate;
        return json(REFRESH_OK);
      },
    });
    renderScreen();

    await screen.findByLabelText('Spot USDMXN'); // el botón se vuelve a montar cuando llega el snapshot
    expect(gets(fetchMock, '/market/snapshots/MKT-LIVE')).toBe(1);
    expect(gets(fetchMock, '/market/snapshots')).toBe(1);

    fireEvent.click(screen.getByRole('button', { name: 'Actualizar datos' }));
    const busy = (await screen.findByRole('button', { name: 'Actualizando…' })) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(posts(fetchMock)).toHaveLength(1);

    release();
    expect((await screen.findByRole('status')).textContent).toBe(
      'Datos al 2026-11-10 · SOFR 2026-11-09 · FRED 2026-11-06',
    );
    await waitFor(() => expect(gets(fetchMock, '/market/snapshots')).toBe(2));
    await waitFor(() => expect(gets(fetchMock, '/market/snapshots/MKT-LIVE')).toBe(2));
    expect((screen.getByRole('button', { name: 'Actualizar datos' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('si MKT-LIVE no existía, el refresco cambia a él y el mensaje lo avisa', async () => {
    const fetchMock = mockBackend({ live: false });
    renderScreen();

    expect(((await screen.findByLabelText('Spot USDMXN')) as HTMLInputElement).value).toBe('18.6');
    expect(gets(fetchMock, '/market/snapshots/MKT-LIVE')).toBe(0);
    expect(screen.queryByRole('note')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Actualizar datos' }));

    expect((await screen.findByRole('status')).textContent).toBe(
      'Datos al 2026-11-10 · SOFR 2026-11-09 · FRED 2026-11-06 · Se cambió a Mercado vivo (SOFR aproximada)',
    );
    await waitFor(() => expect(gets(fetchMock, '/market/snapshots/MKT-LIVE')).toBe(1));
    expect((await screen.findByRole('note')).textContent).toBe(READ_ONLY_NOTE);
    await waitFor(() =>
      expect((screen.getByLabelText('Spot USDMXN') as HTMLInputElement).value).toBe('18.6226'),
    );
  });

  it('si MKT-LIVE ya estaba y el activo es MX-DEMO, el refresco no cambia de snapshot', async () => {
    const fetchMock = mockBackend({ live: true });
    render(
      <SnapshotProvider>
        <PickDemo />
        <MarketScreen />
      </SnapshotProvider>,
    );
    await screen.findByLabelText('Spot USDMXN');
    fireEvent.click(screen.getByRole('button', { name: 'elegir MX-DEMO' }));
    await waitFor(() =>
      expect((screen.getByLabelText('Spot USDMXN') as HTMLInputElement).value).toBe('18.6'),
    );
    const liveGets = gets(fetchMock, '/market/snapshots/MKT-LIVE');
    const demoGets = gets(fetchMock, '/market/snapshots/MX-DEMO');

    fireEvent.click(screen.getByRole('button', { name: 'Actualizar datos' }));

    expect((await screen.findByRole('status')).textContent).toBe(
      'Datos al 2026-11-10 · SOFR 2026-11-09 · FRED 2026-11-06',
    );
    await waitFor(() => expect(gets(fetchMock, '/market/snapshots/MX-DEMO')).toBe(demoGets + 1));
    expect(gets(fetchMock, '/market/snapshots/MKT-LIVE')).toBe(liveGets);
    expect((screen.getByLabelText('Spot USDMXN') as HTMLInputElement).value).toBe('18.6');
    expect(screen.queryByRole('note')).toBeNull();
  });

  it.each([
    [502, 'FRED no respondió: tiempo de espera agotado'],
    [409, 'Ya hay una actualización de datos en curso'],
  ])('un %i del refresco muestra el mensaje del backend tal cual', async (status, message) => {
    mockBackend({ live: true, refresh: () => json({ error: message, field: null }, status) });
    renderScreen();

    await screen.findByLabelText('Spot USDMXN');
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar datos' }));

    expect((await screen.findByRole('alert')).textContent).toBe(message);
    expect(screen.queryByRole('status')).toBeNull();
    expect((screen.getByRole('button', { name: 'Actualizar datos' }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe('MarketScreen · Rodar', () => {
  const ROLLED: Snapshot = { ...SNAPSHOT, id: 'D1', label: 'México demo (sintético) · rodado al 2026-12-08', as_of: '2026-12-08' };

  /** Backend para rodar: POST /market/MX-DEMO/roll responde `roll`; después D1 existe en la lista. */
  function mockRoll(roll: () => Response) {
    let hasD1 = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace(/^\/api/, '');
      if (init?.method === 'POST' && path === '/market/MX-DEMO/roll') {
        const res = roll();
        if (res.status === 201) hasD1 = true;
        return res;
      }
      if (path === '/market/snapshots') {
        return json({ snapshots: hasD1 ? [SNAPSHOT, ROLLED] : [SNAPSHOT] });
      }
      if (path === '/market/snapshots/MX-DEMO') return json(SNAPSHOT);
      if (path === '/market/snapshots/D1' && hasD1) return json(ROLLED);
      return json({ error: 'Snapshot no encontrado', field: null }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);
    return fetchMock;
  }

  const rollPosts = (fetchMock: ReturnType<typeof mockRoll>) =>
    fetchMock.mock.calls.filter(([url, init]) => url === '/api/market/MX-DEMO/roll' && init?.method === 'POST');

  it('Rodar… abre el formulario; enviarlo hace POST del roll y selecciona el nuevo snapshot', async () => {
    const fetchMock = mockRoll(() => json(ROLLED, 201));
    renderScreen();
    await screen.findByLabelText('Spot USDMXN');

    fireEvent.click(screen.getByRole('button', { name: 'Rodar…' }));
    fireEvent.change(screen.getByLabelText('Id nuevo'), { target: { value: 'D1' } });
    fireEvent.change(screen.getByLabelText('Fecha de valuación'), { target: { value: '2026-12-08' } });
    fireEvent.click(screen.getByRole('button', { name: 'Rodar' }));

    await waitFor(() => expect(rollPosts(fetchMock)).toHaveLength(1));
    expect(JSON.parse(String(rollPosts(fetchMock)[0][1]?.body))).toEqual({ id: 'D1', as_of: '2026-12-08' });
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Mercado' })).toBeTruthy());
    await waitFor(() => expect(gets(fetchMock, '/market/snapshots/D1')).toBeGreaterThan(0));
    await waitFor(() => expect(screen.queryByLabelText('Id nuevo')).toBeNull());
  });

  it('un 409 con field "id" aparece bajo "Id nuevo" y no cambia de snapshot', async () => {
    mockRoll(() => json({ error: 'Ya existe un snapshot con ese id', field: 'id' }, 409));
    renderScreen();
    await screen.findByLabelText('Spot USDMXN');

    fireEvent.click(screen.getByRole('button', { name: 'Rodar…' }));
    fireEvent.change(screen.getByLabelText('Id nuevo'), { target: { value: 'MX-DEMO' } });
    fireEvent.change(screen.getByLabelText('Fecha de valuación'), { target: { value: '2026-12-08' } });
    fireEvent.click(screen.getByRole('button', { name: 'Rodar' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Ya existe un snapshot con ese id');
    expect(alert.previousElementSibling?.textContent).toContain('Id nuevo');
    expect((screen.getByLabelText('Id nuevo') as HTMLInputElement).value).toBe('MX-DEMO');
  });
});

// --- corte 3 ---
// Curva MXN-USD y panel «Descuento MXN con colateral en USD».

const CSA_NO_CURVE =
  'El snapshot no trae puntos forward ni base de cross currency swaps: la curva MXN-USD no existe y todo se descuenta con TIIE-F';

const CSA_SNAPSHOT: Snapshot = {
  ...SNAPSHOT,
  curves: {
    ...SNAPSHOT.curves,
    'MXN-USD': {
      currency: 'MXN',
      period_days: 28,
      dependent: true,
      points: [point('1M', 28, 0.0701, 0.0701), point('2Y', 728, 0.0652, 0.0649)],
    },
  },
  fx_forwards: [{ days: 28, points: 0.0438, label: '1M' }],
  xccy_basis: [{ days: 728, spread: -0.001, label: '2Y' }],
  csa: {
    available: true,
    curve: 'MXN-USD',
    source: { kind: 'synthetic', label: 'Sintético (inventado para demostración)', as_of: null },
    message: null,
    implied_vs_quoted: [
      {
        label: '1M',
        days: 28,
        quoted_points: 0.0438,
        quoted_forward: 18.6438,
        implied_forward: 18.6438,
        parity_forward: 18.645095,
        diff: 0,
      },
    ],
  },
};

const CSA_UNAVAILABLE: Snapshot = {
  ...SNAPSHOT,
  fx_forwards: null,
  xccy_basis: null,
  csa: { available: false, curve: 'MXN-USD', source: null, message: CSA_NO_CURVE, implied_vs_quoted: [] },
};

function mockSnapshot(snapshot: Snapshot) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace(/^\/api/, '');
    const body = path === '/market/snapshots' ? { snapshots: [snapshot] } : snapshot;
    return new Response(JSON.stringify(body), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('MarketScreen · colateral y MXN-USD', () => {
  it('con csa.available muestra las tres tablas, el rótulo sintético y MXN-USD entre las curvas', async () => {
    mockSnapshot(CSA_SNAPSHOT);
    renderScreen();

    const csa = await screen.findByRole('region', { name: 'Descuento MXN con colateral en USD' });
    expect(within(csa).getByText('Sintético (inventado para demostración)')).toBeTruthy();
    expect(within(csa).getByRole('table', { name: 'Puntos forward USDMXN' })).toBeTruthy();
    expect(within(csa).getByRole('table', { name: 'Base de cross currency swaps' })).toBeTruthy();
    expect(within(csa).getByRole('table', { name: 'Forward implícito vs cotizado' })).toBeTruthy();

    // La curva dependiente entra en la gráfica de curvas, con su nota y su procedencia, y sin tabla editable.
    const curve = screen.getByRole('region', { name: 'MXN-USD' });
    expect(within(curve).getByRole('img', { name: 'Curva MXN-USD: cero y forward' })).toBeTruthy();
    expect(
      within(curve).getByText(
        'Curva dependiente: se recalibra con los puntos forward y la base fijos cuando se mueven SOFR, TIIE-F o el spot',
      ),
    ).toBeTruthy();
    expect(within(curve).getByText('Sintético (inventado para demostración)')).toBeTruthy();
    expect(curve.querySelector('.market__grid')).toBeNull();
    const names = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(names.indexOf('MXN-USD')).toBeGreaterThan(names.indexOf('SOFR'));
    // TIIE-F y SOFR conservan su tabla de cotizaciones editable.
    expect(screen.getByRole('region', { name: 'TIIE-F' }).querySelector('.market__grid')).toBeTruthy();
  });

  it('sin curva muestra el mensaje y no las tablas ni la curva MXN-USD', async () => {
    mockSnapshot(CSA_UNAVAILABLE);
    renderScreen();

    const csa = await screen.findByRole('region', { name: 'Descuento MXN con colateral en USD' });
    expect(within(csa).getByText(CSA_NO_CURVE)).toBeTruthy();
    expect(screen.queryByRole('table', { name: 'Puntos forward USDMXN' })).toBeNull();
    expect(screen.queryByRole('table', { name: 'Base de cross currency swaps' })).toBeNull();
    expect(screen.queryByRole('table', { name: 'Forward implícito vs cotizado' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'MXN-USD' })).toBeNull();
  });

  it('un snapshot viejo sin csa no rompe ni pinta el panel', async () => {
    mockSnapshot(SNAPSHOT);
    renderScreen();

    await screen.findByRole('region', { name: 'TIIE-F' });
    expect(screen.queryByRole('region', { name: 'Descuento MXN con colateral en USD' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'MXN-USD' })).toBeNull();
  });
});
// --- fin corte 3 ---
