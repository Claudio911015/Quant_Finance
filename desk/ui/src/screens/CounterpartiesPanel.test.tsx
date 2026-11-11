import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Counterparty } from '../api/types';
import CounterpartiesPanel from './CounterpartiesPanel';

const ALFA: Counterparty = {
  id: 1,
  name: 'Banco Alfa (sintético)',
  collateral_currency: 'MXN',
  effective_date: null,
  trades: 3,
  history: [],
};
const BETA: Counterparty = {
  id: 2,
  name: 'Banco Beta (sintético)',
  collateral_currency: 'USD',
  effective_date: '2026-11-10',
  trades: 2,
  history: [
    { id: 4, collateral_currency: 'USD', effective_date: '2026-11-10', created_at: '2026-11-11T18:00:00+00:00' },
  ],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

/** GET /api/counterparties devuelve la lista vigente; PUT responde lo que diga `put`. */
function mockApi(put?: (id: number, body: unknown) => Response, list: Counterparty[] = [ALFA, BETA]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/api/counterparties' && (init?.method ?? 'GET') === 'GET') {
      return json({ counterparties: list });
    }
    const m = /^\/api\/counterparties\/(\d+)$/.exec(url);
    if (m && init?.method === 'PUT') {
      return put ? put(Number(m[1]), JSON.parse(String(init.body))) : json(list[0]);
    }
    return json({ error: 'Ruta inexistente' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const puts = (m: ReturnType<typeof mockApi>) => m.mock.calls.filter((c) => c[1]?.method === 'PUT');
const gets = (m: ReturnType<typeof mockApi>) =>
  m.mock.calls.filter((c) => String(c[0]) === '/api/counterparties' && (c[1]?.method ?? 'GET') === 'GET');

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('CounterpartiesPanel', () => {
  it('lista nombre, operaciones, colateral vigente y desde', async () => {
    mockApi();
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    const alfa = (await screen.findByText('Banco Alfa (sintético)')).closest('tr')!;
    expect(within(alfa).getByText('3')).toBeTruthy();
    expect(within(alfa).getByText('Colateral en MXN')).toBeTruthy();
    // Sin cambios nunca registrados no hay fecha efectiva.
    expect(within(alfa).getByText('—')).toBeTruthy();

    const beta = screen.getByText('Banco Beta (sintético)').closest('tr')!;
    expect(within(beta).getByText('Colateral en USD')).toBeTruthy();
    expect(within(beta).getByText('2026-11-10')).toBeTruthy();
    expect(screen.getByText('2 contrapartes')).toBeTruthy();
  });

  it('el colateral vigente se lee a la fecha de valuación: un cambio posterior se avisa y no se toma por vigente', async () => {
    // Alfa pasó a USD el 2026-11-11, un día después del as_of: al 2026-11-10 su PV sigue en MXN.
    const alfaUsdLater: Counterparty = {
      ...ALFA,
      collateral_currency: 'USD',
      effective_date: '2026-11-11',
      history: [
        { id: 7, collateral_currency: 'USD', effective_date: '2026-11-11', created_at: '2026-11-11T18:00:00+00:00' },
      ],
    };
    mockApi(undefined, [alfaUsdLater, BETA]);
    const { rerender } = render(<CounterpartiesPanel asOf="2026-11-10" />);
    const alfa = (await screen.findByText('Banco Alfa (sintético)')).closest('tr')!;
    expect(within(alfa).getByText('Colateral en MXN')).toBeTruthy();
    expect(within(alfa).queryByText('Colateral en USD')).toBeNull();
    expect(within(alfa).getByText('—')).toBeTruthy();
    expect(within(alfa).getByText('Colateral en USD desde 2026-11-11')).toBeTruthy();

    // A la fecha efectiva ya rige.
    rerender(<CounterpartiesPanel asOf="2026-11-11" />);
    expect(within(alfa).getByText('Colateral en USD')).toBeTruthy();
    expect(within(alfa).getByText('2026-11-11')).toBeTruthy();
    expect(within(alfa).queryByText(/desde 2026-11-11/)).toBeNull();
  });

  it('con varios cambios rige el último con fecha efectiva hasta el as_of, y el siguiente se avisa', async () => {
    const gamma: Counterparty = {
      ...ALFA,
      id: 3,
      name: 'Banco Gamma (sintético)',
      collateral_currency: 'USD',
      effective_date: '2026-12-01',
      history: [
        { id: 8, collateral_currency: 'USD', effective_date: '2026-10-01', created_at: '2026-10-01T18:00:00+00:00' },
        { id: 9, collateral_currency: 'MXN', effective_date: '2026-11-05', created_at: '2026-11-05T18:00:00+00:00' },
        { id: 10, collateral_currency: 'USD', effective_date: '2026-12-01', created_at: '2026-11-11T18:00:00+00:00' },
      ],
    };
    mockApi(undefined, [gamma]);
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    const row = (await screen.findByText('Banco Gamma (sintético)')).closest('tr')!;
    expect(within(row).getByText('Colateral en MXN')).toBeTruthy();
    expect(within(row).getByText('2026-11-05')).toBeTruthy();
    expect(within(row).getByText('Colateral en USD desde 2026-12-01')).toBeTruthy();
  });

  it('el formulario envía la moneda y la fecha efectiva (por omisión el as_of) y recarga', async () => {
    const fetchMock = mockApi();
    const onChanged = vi.fn();
    render(<CounterpartiesPanel asOf="2026-11-10" onChanged={onChanged} />);
    await screen.findByText('Banco Alfa (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Alfa (sintético)' }));
    // Se propone la otra moneda: Alfa tiene MXN, así que USD.
    expect((screen.getByLabelText('Moneda del colateral') as HTMLSelectElement).value).toBe('USD');
    expect((screen.getByLabelText('Fecha efectiva') as HTMLInputElement).value).toBe('2026-11-10');

    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    await waitFor(() => expect(puts(fetchMock)).toHaveLength(1));
    const [url, init] = puts(fetchMock)[0];
    expect(String(url)).toBe('/api/counterparties/1');
    expect(JSON.parse(String(init?.body))).toEqual({ collateral_currency: 'USD', effective_date: '2026-11-10' });
    // Tras el cambio se recarga la lista, se cierra el formulario y se avisa al blotter.
    await waitFor(() => expect(gets(fetchMock)).toHaveLength(2));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(screen.queryByLabelText('Fecha efectiva')).toBeNull();
  });

  it('con la fecha y la moneda cambiadas envía lo elegido', async () => {
    const fetchMock = mockApi();
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Beta (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Beta (sintético)' }));
    expect((screen.getByLabelText('Moneda del colateral') as HTMLSelectElement).value).toBe('MXN');
    fireEvent.change(screen.getByLabelText('Fecha efectiva'), { target: { value: '2026-12-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    await waitFor(() => expect(puts(fetchMock)).toHaveLength(1));
    expect(String(puts(fetchMock)[0][0])).toBe('/api/counterparties/2');
    expect(JSON.parse(String(puts(fetchMock)[0][1]?.body))).toEqual({
      collateral_currency: 'MXN',
      effective_date: '2026-12-01',
    });
  });

  it('un 409 de effective_date aparece bajo la fecha y el formulario sigue abierto', async () => {
    const message = 'La fecha efectiva no puede ser anterior al último cambio (2026-11-10)';
    mockApi(() => json({ error: message, field: 'effective_date' }, 409));
    const onChanged = vi.fn();
    render(<CounterpartiesPanel asOf="2026-11-01" onChanged={onChanged} />);
    await screen.findByText('Banco Beta (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Beta (sintético)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(message);
    const date = screen.getByLabelText('Fecha efectiva');
    expect(date.parentElement?.contains(alert)).toBe(true);
    expect(date.getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByLabelText('Moneda del colateral').getAttribute('aria-invalid')).toBeNull();
    expect(onChanged).not.toHaveBeenCalled();
    expect((screen.getByRole('button', { name: 'Aplicar' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('un 409 de collateral_currency aparece bajo la moneda', async () => {
    const message = 'La contraparte ya tiene colateral en USD';
    mockApi(() => json({ error: message, field: 'collateral_currency' }, 409));
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Beta (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Beta (sintético)' }));
    fireEvent.change(screen.getByLabelText('Moneda del colateral'), { target: { value: 'USD' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(message);
    const currency = screen.getByLabelText('Moneda del colateral');
    expect(currency.parentElement?.contains(alert)).toBe(true);
    expect(currency.getAttribute('aria-invalid')).toBe('true');
  });

  it('un 400 de effective_date también va bajo la fecha', async () => {
    mockApi(() => json({ error: 'effective_date debe ser una fecha ISO (YYYY-MM-DD)', field: 'effective_date' }, 400));
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Alfa (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Alfa (sintético)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    const alert = await screen.findByRole('alert');
    expect(screen.getByLabelText('Fecha efectiva').parentElement?.contains(alert)).toBe(true);
  });

  it('sin fecha no se llama al backend', async () => {
    const fetchMock = mockApi();
    render(<CounterpartiesPanel asOf={null} />);
    await screen.findByText('Banco Alfa (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Alfa (sintético)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    expect((await screen.findByRole('alert')).textContent).toBe('Indica la fecha efectiva');
    expect(puts(fetchMock)).toHaveLength(0);
  });

  it('un fallo que no es de un campo va en el formulario, no bajo un campo', async () => {
    mockApi(() => json({ error: 'Error interno' }, 500));
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Alfa (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Alfa (sintético)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    expect((await screen.findByRole('alert')).textContent).toBe('Error interno');
    expect(screen.getByLabelText('Fecha efectiva').getAttribute('aria-invalid')).toBeNull();
  });

  it('Cancelar cierra el formulario sin llamar al backend', async () => {
    const fetchMock = mockApi();
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Alfa (sintético)');

    fireEvent.click(screen.getByRole('button', { name: 'Cambiar colateral de Banco Alfa (sintético)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByLabelText('Fecha efectiva')).toBeNull();
    expect(puts(fetchMock)).toHaveLength(0);
  });

  it('el historial se despliega con fecha efectiva, moneda y registrado', async () => {
    mockApi();
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Beta (sintético)');
    expect(screen.queryByRole('table', { name: /Historial de colateral/ })).toBeNull();

    const toggle = screen.getByRole('button', { name: 'Historial de Banco Beta (sintético)' });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');

    const table = screen.getByRole('table', { name: 'Historial de colateral de Banco Beta (sintético)' });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((h) => h.textContent);
    expect(headers).toEqual(['Fecha efectiva', 'Moneda', 'Registrado']);
    const row = within(table).getAllByRole('row')[1];
    expect(row.textContent).toContain('2026-11-10');
    expect(row.textContent).toContain('Colateral en USD');
    expect(row.textContent).toContain('2026-11-11 18:00 UTC');

    fireEvent.click(toggle);
    expect(screen.queryByRole('table', { name: /Historial de colateral/ })).toBeNull();
  });

  it('una contraparte sin cambios dice que tiene MXN desde el inicio', async () => {
    mockApi();
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    await screen.findByText('Banco Alfa (sintético)');
    fireEvent.click(screen.getByRole('button', { name: 'Historial de Banco Alfa (sintético)' }));
    expect(
      screen.getByText('Sin cambios registrados: Banco Alfa (sintético) tiene colateral en MXN desde el inicio.'),
    ).toBeTruthy();
  });

  it('si la lista no carga muestra el error del backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ error: 'Base de datos no disponible' }, 500)),
    );
    render(<CounterpartiesPanel asOf="2026-11-10" />);
    expect((await screen.findByRole('alert')).textContent).toBe('Base de datos no disponible');
  });
});
