import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Snapshot, SnapshotSummary, Source, SourceKey, SourceKind } from '../api/types';
import { SOURCE_KEYS } from '../lib/provenance';
import { PRODUCT_SPECS } from '../screens/pricers/registry';
import { SnapshotProvider, useSnapshot } from '../state/SnapshotContext';
import { Shell } from './Shell';

function sourcesOf(kind: SourceKind, as_of: string | null): Record<SourceKey, Source> {
  return Object.fromEntries(
    SOURCE_KEYS.map((key) => [key, { kind, label: `Rótulo ${key}`, as_of }]),
  ) as Record<SourceKey, Source>;
}

const DEMO: SnapshotSummary = {
  id: 'MX-DEMO',
  label: 'México demo (sintético)',
  synthetic: true,
  as_of: '2026-11-10',
  data_quality: 'synthetic',
  sources: sourcesOf('synthetic', null),
};
const MARKET: SnapshotSummary = {
  id: 'MKT-LIVE',
  label: 'Mercado vivo (SOFR aproximada)',
  synthetic: true,
  as_of: '2026-11-11',
  data_quality: 'mixed',
  sources: {
    ...sourcesOf('synthetic', null),
    'curve:SOFR': { kind: 'proxy', label: 'Aproximada: Treasuries par', as_of: '2026-11-10' },
    spot: { kind: 'live', label: 'FRED DEXMXUS', as_of: '2026-11-06' },
    factor_vols: { kind: 'mixed', label: 'SOFR y USDMXN medidas; TIIE-F sintética', as_of: '2026-11-10' },
  },
};
const ALT: SnapshotSummary = {
  id: 'ALT',
  label: 'Mercado alterno',
  synthetic: false,
  as_of: '2026-11-12',
  data_quality: 'live',
  sources: sourcesOf('live', '2026-11-12'),
};

// Solo la cabecera importa para el marco; el resto del snapshot no se lee aquí.
const full = (s: SnapshotSummary) =>
  ({ ...s, read_only: s.id === 'MKT-LIVE', quotes: [], curves: {} }) as unknown as Snapshot;

/** `gate` retiene la respuesta de la lista hasta que se resuelva. */
function mockApi(summaries: SnapshotSummary[], gate?: Promise<void>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace(/^\/api/, '');
    if (path === '/market/snapshots') {
      await gate;
      return new Response(JSON.stringify({ snapshots: summaries }), { status: 200 });
    }
    const found = summaries.find((s) => path === `/market/snapshots/${s.id}`);
    return found
      ? new Response(JSON.stringify(full(found)), { status: 200 })
      : new Response(JSON.stringify({ error: 'Snapshot inexistente', field: 'snapshot' }), { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const snapshotCalls = (m: ReturnType<typeof mockApi>) =>
  m.mock.calls.map((c) => String(c[0])).filter((u) => u.startsWith('/api/market/snapshots/'));

function Where() {
  return <div data-testid="path">{useLocation().pathname}</div>;
}

function Reload() {
  const { reload } = useSnapshot();
  return <button onClick={() => void reload()}>recargar</button>;
}

function renderShell(initialPath = '/mercado') {
  return render(
    <SnapshotProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Shell>
          <Where />
          <Reload />
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

const selector = () => screen.getByLabelText('Fecha de valuación') as HTMLSelectElement;

describe('Shell: barra superior', () => {
  it('cada opción del selector muestra su fecha de valuación', async () => {
    mockApi([DEMO, ALT]);
    renderShell();
    await screen.findByText('Datos sintéticos');

    expect(within(selector()).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'México demo (sintético) · 2026-11-10',
      'Mercado alterno · 2026-11-12',
    ]);
  });

  it('muestra "Datos sintéticos" si la calidad es synthetic', async () => {
    mockApi([DEMO]);
    renderShell();
    expect(await screen.findByText('Datos sintéticos')).toBeTruthy();
    expect(screen.getByText('2026-11-10')).toBeTruthy();
  });

  it('muestra "Datos mixtos" si la calidad es mixed', async () => {
    mockApi([MARKET]);
    renderShell();
    expect(await screen.findByText('Datos mixtos')).toBeTruthy();
    expect(screen.queryByText('Datos sintéticos')).toBeNull();
  });

  it('muestra "Datos de mercado" si la calidad es live, aunque el booleano synthetic sea verdadero', async () => {
    mockApi([{ ...ALT, synthetic: true }]);
    renderShell();
    const badge = await screen.findByText('Datos de mercado');
    expect(badge.className).toContain('shell__badge--live');
    expect(screen.queryByText('Datos sintéticos')).toBeNull();
  });

  it('el tooltip de la insignia trae una línea por componente con tipo, rótulo y fecha', async () => {
    mockApi([MARKET]);
    renderShell();
    const badge = await screen.findByText('Datos mixtos');
    expect(badge.getAttribute('title')?.split('\n')).toEqual([
      'Curva TIIE-F: Sintética — Rótulo curve:TIIE-F (sin fecha)',
      'Curva SOFR: Aproximada — Aproximada: Treasuries par (2026-11-10)',
      'Spot USDMXN: En vivo — FRED DEXMXUS (2026-11-06)',
      'Superficie de volatilidad: Sintética — Rótulo surface (sin fecha)',
      'Parámetros Hull-White: Sintética — Rótulo hw (sin fecha)',
      'Volatilidades de factores: Mixta — SOFR y USDMXN medidas; TIIE-F sintética (2026-11-10)',
      'Correlaciones de factores: Sintética — Rótulo factor_corr (sin fecha)',
    ]);
  });

  it('cambiar el selector carga el otro snapshot y actualiza la insignia', async () => {
    const fetchMock = mockApi([DEMO, ALT]);
    renderShell();
    await screen.findByText('Datos sintéticos');

    fireEvent.change(selector(), { target: { value: 'ALT' } });

    await screen.findByText('2026-11-12');
    expect(fetchMock).toHaveBeenCalledWith('/api/market/snapshots/ALT', expect.anything());
    expect(screen.getByText('Datos de mercado')).toBeTruthy();
    expect(screen.queryByText('Datos sintéticos')).toBeNull();
  });

  it('avisa si el backend no responde', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    renderShell();
    expect((await screen.findByRole('alert')).textContent).toBe('No se pudo conectar con el backend');
  });
});

describe('Snapshot inicial', () => {
  it.each([
    ['primero', [MARKET, DEMO]],
    ['segundo', [DEMO, MARKET]],
  ])('abre en MKT-LIVE si está en la lista (%s)', async (_pos, list) => {
    const fetchMock = mockApi(list);
    renderShell();

    await screen.findByText('Datos mixtos');

    expect(selector().value).toBe('MKT-LIVE');
    expect(snapshotCalls(fetchMock)).toEqual(['/api/market/snapshots/MKT-LIVE']);
  });

  it('sin MKT-LIVE abre en MX-DEMO cuando es el primero', async () => {
    const fetchMock = mockApi([DEMO, ALT]);
    renderShell();

    await screen.findByText('Datos sintéticos');

    expect(selector().value).toBe('MX-DEMO');
    expect(snapshotCalls(fetchMock)).toEqual(['/api/market/snapshots/MX-DEMO']);
  });

  it('sin MKT-LIVE abre en el primero de la lista', async () => {
    const fetchMock = mockApi([ALT, DEMO]);
    renderShell();

    await screen.findByText('Datos de mercado');

    expect(selector().value).toBe('ALT');
    expect(snapshotCalls(fetchMock)).toEqual(['/api/market/snapshots/ALT']);
  });

  it('no pide ningún snapshot completo hasta tener la lista', async () => {
    let open!: () => void;
    const gate = new Promise<void>((resolve) => {
      open = resolve;
    });
    const fetchMock = mockApi([DEMO, MARKET], gate);
    renderShell();
    await act(async () => {});

    expect(fetchMock.mock.calls.map((c) => String(c[0]))).toEqual(['/api/market/snapshots']);

    await act(async () => open());
    await screen.findByText('Datos mixtos');
    expect(snapshotCalls(fetchMock)).toEqual(['/api/market/snapshots/MKT-LIVE']);
  });

  it('recargar la lista no pisa una elección explícita del usuario', async () => {
    const fetchMock = mockApi([DEMO, MARKET]);
    renderShell();
    await screen.findByText('Datos mixtos');

    fireEvent.change(selector(), { target: { value: 'MX-DEMO' } });
    await screen.findByText('Datos sintéticos');
    const listCalls = () => fetchMock.mock.calls.filter((c) => String(c[0]) === '/api/market/snapshots');
    const before = listCalls().length;
    fireEvent.click(screen.getByRole('button', { name: 'recargar' }));

    await waitFor(() => expect(listCalls().length).toBe(before + 1));
    await screen.findByText('Datos sintéticos');
    expect(selector().value).toBe('MX-DEMO');
  });

  it('recargar la lista tampoco repite la elección automática', async () => {
    const list = [DEMO];
    const fetchMock = mockApi(list);
    renderShell();
    await screen.findByText('Datos sintéticos');

    list.push(MARKET); // MKT-LIVE aparece después (p. ej. tras un refresco)
    fireEvent.click(screen.getByRole('button', { name: 'recargar' }));

    await waitFor(() => expect(within(selector()).getAllByRole('option')).toHaveLength(2));
    expect(selector().value).toBe('MX-DEMO');
    expect(snapshotCalls(fetchMock).every((u) => u.endsWith('/MX-DEMO'))).toBe(true);
  });
});

describe('Shell: barra lateral', () => {
  it('enlaza las nueve pantallas, con XVA justo después de Riesgo y Operaciones justo antes de Metodología, y marca la activa', async () => {
    mockApi([DEMO]);
    renderShell('/riesgo');
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((a) => a.textContent)).toEqual([
      'Mercado',
      'Pricers',
      'Portafolio',
      'Riesgo',
      'XVA',
      'Coberturas',
      'Operaciones',
      'Metodología',
      'Validación',
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
  ])('%s abre la paleta con las nueve pantallas y los diez pricers', async (_name, keys) => {
    mockApi([DEMO]);
    renderShell();
    expect(screen.queryByRole('dialog')).toBeNull();

    pressCtrlK(keys);

    const dialog = await screen.findByRole('dialog');
    const specs = Object.values(PRODUCT_SPECS);
    expect(specs).toHaveLength(10);
    const labels = within(dialog)
      .getAllByRole('option')
      .map((o) => o.querySelector('span')?.textContent);
    expect(labels).toEqual([
      'Mercado',
      'Pricers',
      'Portafolio',
      'Riesgo',
      'XVA',
      'Coberturas',
      'Operaciones',
      'Metodología',
      'Validación',
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
