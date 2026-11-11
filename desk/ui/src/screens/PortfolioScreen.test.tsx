import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ValuationResponse } from '../api/types';
import { SnapshotProvider, useSnapshot } from '../state/SnapshotContext';
import { PortfolioScreen, columnDefs, rowTooltip } from './PortfolioScreen';

const VALUATION: ValuationResponse = {
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  total_mxn: 1234567.891,
  rows: [
    {
      id: 1,
      product: 'irs',
      counterparty: 'Banco Alfa',
      trade_date: '2026-11-10',
      start_date: '2026-11-10',
      maturity_date: '2027-11-09',
      status: 'viva',
      notional: 100000000,
      currency: 'MXN',
      maturity: '2027-11-09',
      pv: 1500000.5,
      pv_mxn: 1500000.5,
      error: null,
      warnings: [],
    },
    {
      id: 2,
      product: 'fx_option',
      counterparty: 'Banco Beta',
      trade_date: '2026-11-10',
      start_date: '2026-11-10',
      maturity_date: '2027-02-09',
      status: 'viva',
      notional: 1000000,
      currency: 'USD',
      maturity: '2027-02-09',
      pv: null,
      pv_mxn: null,
      error: 'No se pudo valuar: vol fuera de superficie',
      warnings: [],
    },
    {
      id: 3,
      product: 'irs',
      counterparty: 'Banco Gamma',
      trade_date: '2026-09-01',
      start_date: '2026-09-01',
      maturity_date: '2027-09-01',
      status: 'terminada',
      notional: 50000000,
      currency: 'USD',
      maturity: '2027-09-01',
      pv: 0,
      pv_mxn: 0,
      error: null,
      warnings: [],
    },
    {
      id: 4,
      product: 'irs',
      counterparty: 'Banco Delta',
      trade_date: '2026-10-01',
      start_date: '2026-10-01',
      maturity_date: '2027-10-01',
      status: 'viva',
      notional: 20000000,
      currency: 'MXN',
      maturity: '2027-10-01',
      pv: 10,
      pv_mxn: 10,
      error: null,
      warnings: [
        {
          code: 'missing_fixing',
          index: 'TIIE-F',
          dates: ['2026-11-09'],
          message: 'Falta la fijación TIIE-F del 2026-11-09',
        },
      ],
    },
  ],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function mockApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith('/api/portfolio/valuation')) return json(VALUATION);
    if (url === '/api/market/snapshots') return json({ snapshots: [] });
    return json({ error: 'Snapshot inexistente', field: 'snapshot' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const valuationCalls = (m: ReturnType<typeof mockApi>) =>
  m.mock.calls.map((c) => String(c[0])).filter((u) => u.startsWith('/api/portfolio/valuation'));

function SwitchSnapshot() {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId('OTRO')}>cambiar snapshot</button>;
}

function renderScreen() {
  return render(
    <MemoryRouter initialEntries={['/portafolio']}>
      <SnapshotProvider>
        <SwitchSnapshot />
        <Routes>
          <Route path="/portafolio" element={<PortfolioScreen />} />
          <Route path="/portafolio/:id" element={<p>ficha abierta</p>} />
        </Routes>
      </SnapshotProvider>
    </MemoryRouter>,
  );
}

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

describe('PortfolioScreen', () => {
  it('muestra la fila fija de total con total_mxn', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Alfa');
    const pinned = container.querySelector('.ag-row-pinned');
    expect(pinned?.textContent).toContain('Total');
    expect(pinned?.textContent).toContain('1,234,567.89');
  });

  it('marca las filas con error y conserva el texto del error en el tooltip', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Beta');
    const row = container.querySelector('.ag-row.row-error');
    expect(row?.textContent).toContain('Banco Beta');
    expect(row?.textContent).toContain('Error');
    expect(container.querySelectorAll('.ag-row.row-error')).toHaveLength(1);
  });

  it('vuelve a llamar valuation cuando cambia el snapshot', async () => {
    const fetchMock = mockApi();
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(valuationCalls(fetchMock)).toEqual(['/api/portfolio/valuation?snapshot=MX-DEMO']);

    fireEvent.click(screen.getByText('cambiar snapshot'));
    await waitFor(() =>
      expect(valuationCalls(fetchMock)).toContain('/api/portfolio/valuation?snapshot=OTRO'),
    );
  });

  it('filtrar por estado deja solo esas filas y el total sigue siendo el del backend', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Alfa');
    expect(container.querySelectorAll('.ag-row:not(.ag-row-pinned)')).toHaveLength(4);

    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'terminada' } });

    await waitFor(() => expect(container.querySelectorAll('.ag-row:not(.ag-row-pinned)')).toHaveLength(1));
    const row = container.querySelector('.ag-row:not(.ag-row-pinned)');
    expect(row?.textContent).toContain('Banco Gamma');
    expect(row?.textContent).toContain('Terminada');
    expect(container.querySelector('.ag-row-pinned')?.textContent).toContain('1,234,567.89');

    // Sin coincidencias, el vacío no sugiere agregar operaciones (las hay, solo están filtradas).
    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'ejercida' } });
    await waitFor(() =>
      expect(container.querySelector('.ag-overlay-no-rows-center')?.textContent).toBe(
        'Ninguna operación con ese estado.',
      ),
    );
    // Un solo mensaje: ni el visible ni el que AG Grid anuncia a lectores de pantalla sugieren agregar.
    await waitFor(() => expect(container.textContent).not.toContain('Sin operaciones'));
    // Con filtro activo la fila fija aclara que su total es el de todo el portafolio.
    expect(container.querySelector('.ag-row-pinned')?.textContent).toContain('Total del portafolio');

    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'all' } });
    await waitFor(() => expect(container.querySelectorAll('.ag-row:not(.ag-row-pinned)')).toHaveLength(4));
  });

  it('la fila de total se llama "Total" sin filtro y "Total del portafolio" con un filtro activo', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Alfa');
    const pinned = () => container.querySelector('.ag-row-pinned [col-id="product"]')?.textContent;
    expect(pinned()).toBe('Total');
    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'viva' } });
    await waitFor(() => expect(pinned()).toBe('Total del portafolio'));
    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'all' } });
    await waitFor(() => expect(pinned()).toBe('Total'));
  });

  it('el producto sale con el rótulo en español de Pricers, no con su id', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Alfa');
    const product = (id: number) => container.querySelector(`.ag-row[row-id="${id}"] [col-id="product"]`)?.textContent;
    expect(product(1)).toBe('Swap de tasas (IRS)');
    expect(product(2)).toBe('Opción FX');
    expect(container.textContent).not.toMatch(/\b(irs|fx_option|fx_forward)\b/);
  });

  it('el selector de estado ofrece los cinco estados y "Todas"', async () => {
    mockApi();
    renderScreen();
    await screen.findByText('Banco Alfa');
    const options = Array.from(screen.getByLabelText('Estado').querySelectorAll('option')).map(
      (o) => o.textContent,
    );
    expect(options).toEqual(['Todas', 'No pactada', 'Viva', 'Vencida', 'Terminada', 'Ejercida']);
  });

  it('muestra Pacto, Vencimiento y Estado', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Alfa');
    const headers = Array.from(container.querySelectorAll('.ag-header-cell-text')).map((h) => h.textContent);
    expect(headers).toEqual(expect.arrayContaining(['Pacto', 'Vencimiento', 'Estado']));
    const row = container.querySelector('.ag-row[row-id="1"]');
    expect(row?.textContent).toContain('2026-11-10');
    expect(row?.textContent).toContain('2027-11-09');
    expect(row?.textContent).toContain('Viva');
  });

  it('las columnas caben en 1280 px: la suma de anchos mínimos no pasa de 1025 px (1280 − barra lateral − márgenes − barra de desplazamiento)', () => {
    const min = columnDefs.map((c) => (c.flex ? (c.minWidth ?? 0) : (c.width ?? 0)));
    expect(min.every((w) => w > 0)).toBe(true);
    expect(min.reduce((a, b) => a + b, 0)).toBeLessThanOrEqual(1025);
  });

  it('la columna PV lleva la moneda de pv: MXN para FX y la de la curva para tasas', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Alfa');
    const pv = (id: number) => container.querySelector(`.ag-row[row-id="${id}"] [col-id="pv"]`)?.textContent;
    expect(pv(1)).toBe('MXN 1,500,000.50');
    expect(pv(3)).toBe('USD 0.00');
    expect(pv(2)).toBe('Error');
  });

  it('el id es un enlace a la ficha y el clic navega sin recargar', async () => {
    mockApi();
    renderScreen();
    await screen.findByText('Banco Alfa');
    const link = await screen.findByRole('link', { name: '1' });
    expect(link.getAttribute('href')).toBe('/portafolio/1');

    // fireEvent devuelve false si el manejador canceló la acción por defecto (recarga completa).
    expect(fireEvent.click(link)).toBe(false);

    expect(await screen.findByText('ficha abierta')).toBeTruthy();
  });

  it('no hay botón de borrar: las operaciones se terminan desde la ficha', async () => {
    const fetchMock = mockApi();
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(screen.queryByText('Borrar')).toBeNull();
    expect(screen.queryByLabelText(/Borrar operación/)).toBeNull();
    expect(fetchMock.mock.calls.filter((c) => c[1]?.method === 'DELETE')).toHaveLength(0);
  });

  it('marca las filas con avisos y el tooltip lleva su texto', async () => {
    mockApi();
    const { container } = renderScreen();
    await screen.findByText('Banco Delta');
    const warn = container.querySelectorAll('.ag-row.row-warn');
    expect(warn).toHaveLength(1);
    expect(warn[0].textContent).toContain('Banco Delta');
    expect(rowTooltip(VALUATION.rows[3])).toBe('Falta la fijación TIIE-F del 2026-11-09');
    expect(rowTooltip(VALUATION.rows[1])).toBe('No se pudo valuar: vol fuera de superficie');
    expect(rowTooltip(VALUATION.rows[0])).toBeUndefined();
  });
});
