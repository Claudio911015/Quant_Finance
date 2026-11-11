import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Snapshot, Source } from '../api/types';
import { SnapshotProvider } from '../state/SnapshotContext';
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
});
