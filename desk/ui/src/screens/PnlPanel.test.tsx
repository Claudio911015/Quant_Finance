import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PnlResponse, SnapshotSummary } from '../api/types';
import { SnapshotProvider } from '../state/SnapshotContext';
import PnlPanel, { columnDefs } from './PnlPanel';

const SOURCES = {} as SnapshotSummary['sources'];

// "C" va primero: es el que el proveedor deja activo. "B" es el anterior más cercano a "C".
const SNAPSHOTS: SnapshotSummary[] = [
  { id: 'C', label: 'Cierre C', synthetic: true, as_of: '2026-12-08', data_quality: 'synthetic', sources: SOURCES },
  { id: 'A', label: 'Cierre A', synthetic: true, as_of: '2026-10-10', data_quality: 'synthetic', sources: SOURCES },
  { id: 'B', label: 'Cierre B', synthetic: true, as_of: '2026-11-10', data_quality: 'synthetic', sources: SOURCES },
];

const PNL: PnlResponse = {
  from: { snapshot: 'B', as_of: '2026-11-10' },
  to: { snapshot: 'C', as_of: '2026-12-08' },
  total_mxn: 1500000.25,
  totals: { pv_from: 9000000.5, pv_to: 10000000.5, settled: 500000, pnl: 1500000.25 },
  rows: [
    {
      id: 1,
      product: 'irs',
      counterparty: 'Banco Alfa',
      status_from: 'viva',
      status_to: 'viva',
      pv_from: 6000000.5,
      pv_to: 6500000.5,
      settled: 300000,
      pnl: 800000,
      error: null,
      warnings: [
        { code: 'missing_fixing', index: 'TIIE-F', dates: ['2026-11-20'], message: 'Falta la fijación TIIE-F del 2026-11-20' },
      ],
    },
    {
      id: 2,
      product: 'fx_forward',
      counterparty: 'Banco Beta',
      status_from: 'no_pactada',
      status_to: 'terminada',
      pv_from: 0,
      pv_to: 0,
      settled: 200000,
      pnl: 200000,
      error: null,
      warnings: [],
    },
    {
      id: 3,
      product: 'bond',
      counterparty: 'Banco Gamma',
      status_from: 'viva',
      status_to: 'viva',
      pv_from: 3000000,
      pv_to: 3500000.25,
      settled: 0,
      pnl: 500000.25,
      error: null,
      warnings: [],
    },
    {
      id: 4,
      product: 'swaption',
      counterparty: 'Banco Delta',
      status_from: 'viva',
      status_to: 'viva',
      pv_from: null,
      pv_to: null,
      settled: null,
      pnl: null,
      error: 'No se pudo valuar: vol fuera de superficie',
      warnings: [],
    },
  ],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function mockApi(pnlResponse: () => Response = () => json(PNL)) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === '/api/market/snapshots') return json({ snapshots: SNAPSHOTS });
    if (url.startsWith('/api/pnl')) return pnlResponse();
    return json({ error: 'Snapshot inexistente', field: 'snapshot' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const pnlCalls = (m: ReturnType<typeof mockApi>) =>
  m.mock.calls.map((c) => String(c[0])).filter((u) => u.startsWith('/api/pnl'));

function renderPanel() {
  return render(
    <SnapshotProvider>
      <PnlPanel />
    </SnapshotProvider>,
  );
}

/** Espera a que la lista de snapshots llegue y devuelve los dos selectores. */
async function selectors() {
  await screen.findAllByRole('option', { name: 'Cierre B · 2026-11-10' });
  return {
    from: screen.getByLabelText('Desde') as HTMLSelectElement,
    to: screen.getByLabelText('Hasta') as HTMLSelectElement,
  };
}

const cellText = (el: Element) => el.textContent?.trim() ?? '';
const parseMoney = (s: string) => Number(s.replace(/,/g, ''));

beforeEach(() => {
  // jsdom no trae ResizeObserver, que AG Grid usa para medir el contenedor.
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('PnlPanel', () => {
  it('"Hasta" arranca en el snapshot activo y "Desde" en el de fecha anterior más cercana', async () => {
    mockApi();
    renderPanel();
    const { from, to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));
    expect(from.value).toBe('B');
    // Cada selector lista los mismos snapshots como `label · as_of`.
    expect(screen.getAllByRole('option', { name: 'Cierre C · 2026-12-08' })).toHaveLength(2);
  });

  it('la tabla vacía habla español, no el "No Rows To Show" de AG Grid', async () => {
    mockApi();
    const { container } = renderPanel();
    await selectors();
    await waitFor(() => expect(container.querySelector('.ag-overlay-no-rows-center')).not.toBeNull());
    expect(container.querySelector('.ag-overlay-no-rows-center')?.textContent).toBe(
      'Sin resultados: elige las fechas y presiona Calcular.',
    );
  });

  it('sin snapshot anterior deja "Desde" vacío y no deja calcular', async () => {
    mockApi();
    renderPanel();
    const { from, to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));
    fireEvent.change(to, { target: { value: 'A' } });
    expect(from.value).toBe('');
    expect((screen.getByRole('button', { name: 'Calcular' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('Calcular llama /api/pnl con los dos snapshots y la fila total muestra totals.pnl', async () => {
    const fetchMock = mockApi();
    const { container } = renderPanel();
    const { to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));

    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));
    await screen.findByText('Banco Alfa');

    expect(pnlCalls(fetchMock)).toEqual(['/api/pnl?from=B&to=C']);
    const pinned = container.querySelector('.ag-row-pinned');
    expect(pinned?.textContent).toContain('Total');
    expect(cellText(pinned!.querySelector('[col-id="pnl"]')!)).toBe('1,500,000.25');
    expect(cellText(pinned!.querySelector('[col-id="pv_from"]')!)).toBe('9,000,000.50');
    expect(cellText(pinned!.querySelector('[col-id="settled"]')!)).toBe('500,000.00');
  });

  it('el producto sale con el rótulo en español de Pricers, no con su id', async () => {
    mockApi();
    const { container } = renderPanel();
    const { to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));
    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));
    await screen.findByText('Banco Alfa');
    const product = (id: number) => container.querySelector(`.ag-row[row-id="${id}"] [col-id="product"]`)?.textContent;
    expect([1, 2, 3, 4].map(product)).toEqual(['Swap de tasas (IRS)', 'Forward FX', 'Bono', 'Swaption']);
    expect(container.textContent).not.toMatch(/\b(irs|fx_forward)\b/);
    expect(container.querySelector('.ag-row-pinned [col-id="product"]')?.textContent).toBe('Total');
  });

  it('un P&L que redondea a cero se muestra 0.00, nunca -0.00', async () => {
    const tiny = { ...PNL, rows: [{ ...PNL.rows[0], pv_from: -0.001, pnl: -0 }], totals: { ...PNL.totals, pv_from: -0.0004 } };
    mockApi(() => json(tiny));
    const { container } = renderPanel();
    const { to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));
    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));
    await screen.findByText('Banco Alfa');
    expect(cellText(container.querySelector('.ag-row[row-id="1"] [col-id="pv_from"]')!)).toBe('0.00');
    expect(cellText(container.querySelector('.ag-row[row-id="1"] [col-id="pnl"]')!)).toBe('0.00');
    expect(cellText(container.querySelector('.ag-row-pinned [col-id="pv_from"]')!)).toBe('0.00');
    expect(container.textContent).not.toContain('-0.00');
  });

  it('las columnas caben en 1280 px: la suma de anchos mínimos no pasa de 1025 px (1280 − barra lateral − márgenes − barra de desplazamiento)', () => {
    const min = columnDefs.map((c) => (c.flex ? (c.minWidth ?? 0) : (c.width ?? 0)));
    expect(min.every((w) => w > 0)).toBe(true);
    expect(min.reduce((a, b) => a + b, 0)).toBeLessThanOrEqual(1025);
  });

  it('la suma de las filas sin error es igual al total y la fila con error se marca', async () => {
    mockApi();
    const { container } = renderPanel();
    const { to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));

    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));
    await screen.findByText('Banco Delta');

    const body = Array.from(container.querySelectorAll('.ag-row:not(.ag-row-pinned)'));
    expect(body).toHaveLength(4);
    const sum = body
      .filter((r) => !r.classList.contains('row-error'))
      .map((r) => parseMoney(cellText(r.querySelector('[col-id="pnl"]')!)))
      .reduce((a, b) => a + b, 0);
    const total = parseMoney(cellText(container.querySelector('.ag-row-pinned [col-id="pnl"]')!));
    expect(sum).toBeCloseTo(total, 2);

    const errRow = container.querySelectorAll('.ag-row.row-error');
    expect(errRow).toHaveLength(1);
    expect(errRow[0].textContent).toContain('Banco Delta');
    expect(cellText(errRow[0].querySelector('[col-id="pnl"]')!)).toBe('Error');
    // La fila con avisos lleva su marca; los estados salen rotulados.
    expect(container.querySelectorAll('.ag-row.row-warn')).toHaveLength(1);
    expect(screen.getByText('No pactada')).toBeTruthy();
    expect(screen.getByText('Terminada')).toBeTruthy();
  });

  it('un 400 con field "to" aparece junto a "Hasta" y no junto a "Desde"', async () => {
    mockApi(() => json({ error: 'La fecha de "Hasta" no puede ser anterior a la de "Desde"', field: 'to' }, 400));
    renderPanel();
    const { from, to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));

    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('no puede ser anterior');
    expect(to.closest('.pnl__field')?.contains(alert)).toBe(true);
    expect(from.closest('.pnl__field')?.contains(alert)).toBe(false);
    expect(to.getAttribute('aria-invalid')).toBe('true');
    expect(from.getAttribute('aria-invalid')).toBeNull();
  });

  it('un error sin selector propio (snapshot inexistente) sale en un aviso general', async () => {
    mockApi(() => json({ error: 'Snapshot inexistente', field: 'snapshot' }, 404));
    const { container } = renderPanel();
    const { to } = await selectors();
    await waitFor(() => expect(to.value).toBe('C'));

    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Snapshot inexistente');
    expect(alert.classList.contains('pnl__banner')).toBe(true);
    expect(container.querySelector('.pnl__field [role="alert"]')).toBeNull();
  });
});
