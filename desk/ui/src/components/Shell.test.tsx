import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Snapshot, SnapshotSummary } from '../api/types';
import { PRODUCT_SPECS } from '../screens/pricers/registry';
import { SnapshotProvider } from '../state/SnapshotContext';
import { Shell } from './Shell';

const DEMO: SnapshotSummary = {
  id: 'MX-DEMO',
  label: 'México demo (sintético)',
  synthetic: true,
  as_of: '2026-11-10',
};
const LIVE: SnapshotSummary = { id: 'LIVE', label: 'Mercado en vivo', synthetic: false, as_of: '2026-11-11' };

// Solo la cabecera importa para el marco; el resto del snapshot no se lee aquí.
const full = (s: SnapshotSummary) => ({ ...s, quotes: [], curves: {} }) as unknown as Snapshot;

function mockApi(summaries: SnapshotSummary[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace(/^\/api/, '');
    const found = summaries.find((s) => path === `/market/snapshots/${s.id}`);
    const body =
      path === '/market/snapshots' ? { snapshots: summaries } : found ? full(found) : null;
    return body
      ? new Response(JSON.stringify(body), { status: 200 })
      : new Response(JSON.stringify({ error: 'Snapshot inexistente', field: 'snapshot' }), { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function Where() {
  return <div data-testid="path">{useLocation().pathname}</div>;
}

function renderShell(initialPath = '/mercado') {
  return render(
    <SnapshotProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Shell>
          <Where />
        </Shell>
      </MemoryRouter>
    </SnapshotProvider>,
  );
}

const pressCtrlK = (extra: { ctrlKey?: boolean; metaKey?: boolean } = { ctrlKey: true }) =>
  fireEvent.keyDown(window, { key: 'k', ...extra });

beforeAll(() => {
  // jsdom no trae scrollIntoView, que cmdk usa para mantener visible la fila elegida.
  Element.prototype.scrollIntoView = vi.fn();
});

beforeEach(() => {
  // ni ResizeObserver, con el que cmdk dimensiona la lista.
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
});

describe('Shell: barra superior', () => {
  it('muestra "Datos sintéticos" si el snapshot lo es', async () => {
    mockApi([DEMO]);
    renderShell();
    expect(await screen.findByText('Datos sintéticos')).toBeTruthy();
    expect(screen.getByText('2026-11-10')).toBeTruthy();
  });

  it('no muestra el distintivo si el snapshot no es sintético', async () => {
    mockApi([{ ...DEMO, id: 'MX-DEMO', synthetic: false }]);
    renderShell();
    await screen.findByText('2026-11-10');
    expect(screen.queryByText('Datos sintéticos')).toBeNull();
  });

  it('cambiar el selector carga el otro snapshot y actualiza el distintivo', async () => {
    const fetchMock = mockApi([DEMO, LIVE]);
    renderShell();
    await screen.findByText('Datos sintéticos');

    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'LIVE' } });

    await screen.findByText('2026-11-11');
    expect(fetchMock).toHaveBeenCalledWith('/api/market/snapshots/LIVE', expect.anything());
    expect(screen.queryByText('Datos sintéticos')).toBeNull();
  });

  it('avisa si el backend no responde', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    renderShell();
    expect((await screen.findByRole('alert')).textContent).toBe('No se pudo conectar con el backend');
  });
});

describe('Shell: barra lateral', () => {
  it('enlaza las cinco pantallas y marca la activa', async () => {
    mockApi([DEMO]);
    renderShell('/riesgo');
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((a) => a.textContent)).toEqual([
      'Mercado',
      'Pricers',
      'Portafolio',
      'Riesgo',
      'Metodología',
    ]);
    expect(within(nav).getByRole('link', { name: 'Riesgo' }).getAttribute('aria-current')).toBe('page');
    expect(within(nav).getByRole('link', { name: 'Mercado' }).getAttribute('aria-current')).toBeNull();
    await screen.findByText('Datos sintéticos');
  });
});

describe('Paleta de comandos', () => {
  it.each([
    ['Ctrl+K', { ctrlKey: true }],
    ['Cmd+K', { metaKey: true }],
  ])('%s abre la paleta con las cinco pantallas y los siete pricers', async (_name, keys) => {
    mockApi([DEMO]);
    renderShell();
    expect(screen.queryByRole('dialog')).toBeNull();

    pressCtrlK(keys);

    const dialog = await screen.findByRole('dialog');
    const specs = Object.values(PRODUCT_SPECS);
    expect(specs).toHaveLength(7);
    const labels = within(dialog)
      .getAllByRole('option')
      .map((o) => o.querySelector('span')?.textContent);
    expect(labels).toEqual([
      'Mercado',
      'Pricers',
      'Portafolio',
      'Riesgo',
      'Metodología',
      ...specs.map((spec) => spec.title),
    ]);
    await screen.findByText('Datos sintéticos');
  });

  it('el botón de la barra superior también la abre', async () => {
    mockApi([DEMO]);
    renderShell();
    fireEvent.click(screen.getByRole('button', { name: /Buscar o ir a/ }));
    expect(await screen.findByRole('dialog')).toBeTruthy();
    await screen.findByText('Datos sintéticos');
  });

  it('Esc la cierra', async () => {
    mockApi([DEMO]);
    renderShell();
    pressCtrlK();
    await screen.findByRole('dialog');

    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await screen.findByText('Datos sintéticos');
  });

  it('Enter en una pantalla filtrada navega y cierra', async () => {
    mockApi([DEMO]);
    renderShell();
    pressCtrlK();
    const input = await screen.findByRole('combobox');

    fireEvent.change(input, { target: { value: 'metod' } });
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(1));
    expect(screen.getByRole('option').getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/metodologia'));
    expect(screen.queryByRole('dialog')).toBeNull();
    await screen.findByText('Datos sintéticos');
  });

  it('Enter en un pricer navega a su ruta', async () => {
    mockApi([DEMO]);
    renderShell();
    pressCtrlK();
    const input = await screen.findByRole('combobox');

    fireEvent.change(input, { target: { value: 'swaption' } });
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(1));
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/pricers/swaption'));
    await screen.findByText('Datos sintéticos');
  });
});
