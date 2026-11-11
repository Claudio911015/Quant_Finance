import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ValuationResponse } from '../api/types';
import { SnapshotProvider, useSnapshot } from '../state/SnapshotContext';
import { PortfolioScreen } from './PortfolioScreen';

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
  ],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function mockApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith('/api/portfolio/valuation')) return json(VALUATION);
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
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
    <SnapshotProvider>
      <SwitchSnapshot />
      <PortfolioScreen />
    </SnapshotProvider>,
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

  it('borra una operación tras confirmar y recarga la valuación', async () => {
    const fetchMock = mockApi();
    vi.stubGlobal('confirm', vi.fn(() => true));
    renderScreen();
    await screen.findByText('Banco Alfa');

    fireEvent.click(await screen.findByLabelText('Borrar operación 1'));

    await waitFor(() => expect(valuationCalls(fetchMock)).toHaveLength(2));
    const deletes = fetchMock.mock.calls.filter((c) => c[1]?.method === 'DELETE');
    expect(deletes.map((c) => String(c[0]))).toEqual(['/api/trades/1']);
  });

  it('no borra si se cancela la confirmación', async () => {
    const fetchMock = mockApi();
    vi.stubGlobal('confirm', vi.fn(() => false));
    renderScreen();
    await screen.findByText('Banco Alfa');

    fireEvent.click(await screen.findByLabelText('Borrar operación 1'));

    expect(fetchMock.mock.calls.filter((c) => c[1]?.method === 'DELETE')).toHaveLength(0);
    expect(valuationCalls(fetchMock)).toHaveLength(1);
  });
});
