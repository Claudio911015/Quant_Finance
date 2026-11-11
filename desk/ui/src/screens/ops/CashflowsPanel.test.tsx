import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { cashflowsCsvUrl, confirmSettlement, getCashflows } from '../../api/opsClient';
import type { CashflowRow, CashflowsResponse } from '../../api/opsTypes';
import { CashflowsPanel } from './CashflowsPanel';

vi.mock('../../api/opsClient');

const snapshotState = {
  snapshotId: 'MX-DEMO',
  snapshot: { id: 'MX-DEMO', as_of: '2026-11-10' } as { id: string; as_of: string } | null,
};

vi.mock('../../state/SnapshotContext', () => ({ useSnapshot: () => snapshotState }));

function row(over: Partial<CashflowRow>): CashflowRow {
  return {
    date: '2026-11-03',
    trade_id: 1,
    counterparty: 'Banco Alfa (sintético)',
    product: 'irs',
    kind: 'coupon',
    status: 'settled',
    currency: 'MXN',
    amount: 31000,
    amount_mxn: 31000,
    df: null,
    pv: null,
    confirmed_amount: null,
    difference: null,
    ...over,
  };
}

const RESPONSE: CashflowsResponse = {
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  from: '2026-08-12',
  to: null,
  counterparty: null,
  currency: null,
  rows: [
    // Liquidado sin confirmar: admite el botón.
    row({ date: '2026-11-03', trade_id: 1 }),
    // Liquidado y confirmado: muestra confirmado y diferencia, sin botón.
    row({
      date: '2026-10-06',
      trade_id: 1,
      status: 'confirmed',
      confirmed_amount: 30990,
      difference: -10,
    }),
    // Liquidación en USD de otra contraparte.
    row({
      date: '2026-11-05',
      trade_id: 4,
      counterparty: 'Banco Beta (sintético)',
      product: 'fx_forward',
      kind: 'settlement',
      currency: 'USD',
      amount: -2500,
      amount_mxn: -46000,
    }),
    // Transferencia liquidada: no es cupón ni liquidación, sin botón.
    row({ date: '2026-11-04', trade_id: 2, kind: 'transfer', amount: 100, amount_mxn: 100 }),
    // Proyectado: sin botón.
    row({
      date: '2026-12-08',
      trade_id: 1,
      status: 'projected',
      amount: -152340.12,
      amount_mxn: -152340.12,
      df: 0.99412,
      pv: -151444.3,
    }),
  ],
  totals: {
    amount_mxn: -259586.12,
    by_date: [],
    by_counterparty: [
      { counterparty: 'Banco Alfa (sintético)', amount_mxn: -213586.12, count: 4 },
      { counterparty: 'Banco Beta (sintético)', amount_mxn: -46000, count: 1 },
    ],
    by_currency: [
      { currency: 'MXN', amount: -213586.12, amount_mxn: -213586.12, count: 4 },
      { currency: 'USD', amount: -2500, amount_mxn: -46000, count: 1 },
    ],
  },
  errors: [{ trade_id: 9, message: 'No se pudo derivar sus flujos: falta la curva' }],
  warnings: [
    {
      code: 'missing_fixing',
      index: 'TIIE-F',
      dates: ['2026-11-05'],
      message: 'Falta la fijación TIIE-F',
    },
  ],
};

function renderPanel() {
  return render(
    <MemoryRouter initialEntries={['/operaciones']}>
      <Routes>
        <Route path="/operaciones" element={<CashflowsPanel />} />
        <Route path="/portafolio/:id" element={<p>ficha abierta</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Espera a que la tabla de flujos esté pintada. */
async function loaded() {
  await screen.findByRole('table', { name: 'Flujos' });
}

/** Fila de la tabla principal (la de flujos) por el texto de su celda de fecha y operación. */
function flowRow(date: string, tradeId: number): HTMLElement {
  const table = screen.getByRole('table', { name: 'Flujos' });
  const found = within(table)
    .getAllByRole('row')
    .find((r) => {
      const cells = within(r).queryAllByRole('cell');
      return cells.length > 2 && cells[0].textContent === date && cells[1].textContent === `#${tradeId}`;
    });
  if (!found) throw new Error(`sin fila ${date} #${tradeId}`);
  return found;
}

beforeEach(() => {
  snapshotState.snapshotId = 'MX-DEMO';
  snapshotState.snapshot = { id: 'MX-DEMO', as_of: '2026-11-10' };
  vi.mocked(getCashflows).mockResolvedValue(RESPONSE);
  vi.mocked(cashflowsCsvUrl).mockReturnValue('/api/cashflows?snapshot=MX-DEMO&format=csv');
});

afterEach(() => {
  vi.resetAllMocks();
});

describe('CashflowsPanel', () => {
  it('consulta desde el as_of menos 90 días, sin límite superior, y pinta filas y totales', async () => {
    renderPanel();
    await loaded();

    expect(getCashflows).toHaveBeenCalledWith({ snapshot: 'MX-DEMO', from: '2026-08-12' });
    expect((screen.getByLabelText('Desde') as HTMLInputElement).value).toBe('2026-08-12');
    expect((screen.getByLabelText('Hasta') as HTMLInputElement).value).toBe('');

    expect(screen.getByText('5 flujos', { exact: false })).toBeTruthy();
    const proj = within(flowRow('2026-12-08', 1));
    expect(proj.getByText('Proyectado')).toBeTruthy();
    expect(proj.getAllByText('-152,340.12').length).toBe(2);
    expect(within(flowRow('2026-11-05', 4)).getByText('Forward USD/MXN')).toBeTruthy();
    expect(within(flowRow('2026-11-05', 4)).getByText('Liquidación')).toBeTruthy();

    const totals = within(screen.getByRole('region', { name: 'Totales' }));
    expect(totals.getByText('MXN -259,586.12')).toBeTruthy();
    const byCurrency = within(totals.getByRole('table', { name: 'Totales por moneda' }));
    expect(byCurrency.getByText('USD')).toBeTruthy();
    expect(byCurrency.getByText('-2,500.00')).toBeTruthy();
    const byCp = within(totals.getByRole('table', { name: 'Totales por contraparte' }));
    expect(byCp.getByText('Banco Alfa (sintético)')).toBeTruthy();
    expect(byCp.getByText('-213,586.12')).toBeTruthy();
  });

  it('el número de operación enlaza a su ficha', async () => {
    renderPanel();
    await loaded();
    const link = within(flowRow('2026-11-05', 4)).getByRole('link', { name: '#4' });
    expect(link.getAttribute('href')).toBe('/portafolio/4');
  });

  it('muestra errores por operación y avisos de fijaciones', async () => {
    renderPanel();
    await loaded();
    expect(screen.getByText('Operación 9: No se pudo derivar sus flujos: falta la curva')).toBeTruthy();
    const avisos = within(screen.getByRole('list', { name: 'Avisos' }));
    expect(avisos.getByText('Falta la fijación TIIE-F', { exact: false })).toBeTruthy();
    expect(avisos.getByText('(2026-11-05)')).toBeTruthy();
  });

  it('un aviso con muchas fechas muestra las primeras y cuenta el resto, sin listar los 117 días', async () => {
    const dates = Array.from({ length: 117 }, (_, i) => {
      const d = new Date(Date.UTC(2026, 6, 1 + i));
      return d.toISOString().slice(0, 10);
    });
    vi.mocked(getCashflows).mockResolvedValue({
      ...RESPONSE,
      warnings: [{ code: 'missing_fixing', index: 'TIIE-F', dates, message: 'Faltan fijaciones de TIIE-F en 117 día(s)' }],
    });
    renderPanel();
    await loaded();
    const avisos = screen.getByRole('list', { name: 'Avisos' });
    expect(within(avisos).getByText('Faltan fijaciones de TIIE-F en 117 día(s)', { exact: false })).toBeTruthy();
    const note = within(avisos).getByText('y 112 más', { exact: false });
    expect(note.textContent).toContain(dates[0]);
    expect(note.textContent).toContain(dates[4]);
    expect(note.textContent).not.toContain(dates[5]);
    // la lista completa sigue disponible al pasar el cursor
    expect(note.getAttribute('title')).toContain(dates[116]);
  });

  it('cambiar Moneda a USD vuelve a consultar con currency USD', async () => {
    renderPanel();
    await loaded();

    fireEvent.change(screen.getByLabelText('Moneda'), { target: { value: 'USD' } });

    await waitFor(() =>
      expect(getCashflows).toHaveBeenLastCalledWith({
        snapshot: 'MX-DEMO',
        from: '2026-08-12',
        currency: 'USD',
      }),
    );
  });

  it('las contrapartes del filtro salen de las filas y elegir una la manda en la consulta', async () => {
    renderPanel();
    await loaded();

    const select = screen.getByLabelText('Contraparte') as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual([
      'Todas',
      'Banco Alfa (sintético)',
      'Banco Beta (sintético)',
    ]);

    // La respuesta ya filtrada no encoge la lista: se conserva la de la consulta sin contraparte.
    vi.mocked(getCashflows).mockResolvedValue({
      ...RESPONSE,
      counterparty: 'Banco Beta (sintético)',
      rows: [RESPONSE.rows[2]],
    });
    fireEvent.change(select, { target: { value: 'Banco Beta (sintético)' } });
    await waitFor(() =>
      expect(getCashflows).toHaveBeenLastCalledWith({
        snapshot: 'MX-DEMO',
        from: '2026-08-12',
        counterparty: 'Banco Beta (sintético)',
      }),
    );
    await waitFor(() => expect(screen.getByText('1 flujo', { exact: false })).toBeTruthy());
    expect(select.options.length).toBe(3);
  });

  it('borrar "Desde" quita el límite inferior', async () => {
    renderPanel();
    await loaded();

    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '' } });
    await waitFor(() => expect(getCashflows).toHaveBeenLastCalledWith({ snapshot: 'MX-DEMO' }));

    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-12-31' } });
    await waitFor(() =>
      expect(getCashflows).toHaveBeenLastCalledWith({ snapshot: 'MX-DEMO', to: '2026-12-31' }),
    );
  });

  it('una fila confirmada muestra el monto confirmado y la diferencia', async () => {
    renderPanel();
    await loaded();

    const cells = within(flowRow('2026-10-06', 1)).getAllByRole('cell');
    expect(within(flowRow('2026-10-06', 1)).getByText('Confirmado')).toBeTruthy();
    expect(cells[9].textContent).toBe('30,990.00');
    expect(cells[10].textContent).toBe('-10.00');
    // Una fila sin confirmar no inventa montos: guion en vez de cifra.
    const plain = within(flowRow('2026-11-03', 1)).getAllByRole('cell');
    expect(plain[9].textContent).toBe('—');
    expect(plain[10].textContent).toBe('—');
  });

  it('el botón solo aparece en filas liquidadas de cupón o liquidación', async () => {
    renderPanel();
    await loaded();

    const has = (date: string, id: number) =>
      within(flowRow(date, id)).queryByRole('button', { name: 'Confirmar liquidación' }) !== null;
    expect(has('2026-11-03', 1)).toBe(true); // liquidado, cupón
    expect(has('2026-11-05', 4)).toBe(true); // liquidado, liquidación
    expect(has('2026-10-06', 1)).toBe(false); // ya confirmado
    expect(has('2026-11-04', 2)).toBe(false); // transferencia
    expect(has('2026-12-08', 1)).toBe(false); // proyectado
    expect(screen.getAllByRole('button', { name: 'Confirmar liquidación' })).toHaveLength(2);
  });

  it('el formulario viene con el monto calculado y la moneda del flujo; enviarlo confirma y recarga', async () => {
    vi.mocked(confirmSettlement).mockResolvedValue({
      event: {} as never,
      flow: { date: '2026-11-05', kind: 'settlement', amount: -2500, currency: 'USD' },
      difference: -10,
    });
    renderPanel();
    await loaded();
    const before = vi.mocked(getCashflows).mock.calls.length;

    fireEvent.click(within(flowRow('2026-11-05', 4)).getByRole('button', { name: 'Confirmar liquidación' }));
    const form = within(screen.getByRole('form'));
    const input = form.getByLabelText('Monto liquidado por el banco') as HTMLInputElement;
    expect(input.value).toBe('-2500.00');
    expect(form.getByText('USD')).toBeTruthy();

    fireEvent.change(input, { target: { value: '-2,510.50' } });
    fireEvent.click(form.getByRole('button', { name: 'Confirmar' }));

    await waitFor(() =>
      expect(confirmSettlement).toHaveBeenCalledWith(4, {
        date: '2026-11-05',
        amount: -2510.5,
        currency: 'USD',
        snapshot: 'MX-DEMO',
      }),
    );
    await waitFor(() => expect(vi.mocked(getCashflows).mock.calls.length).toBe(before + 1));
    // Tras recargar, el formulario se cierra.
    await waitFor(() => expect(screen.queryByRole('form')).toBeNull());
  });

  it('un 409 del backend se muestra junto al formulario y lo deja abierto', async () => {
    vi.mocked(confirmSettlement).mockRejectedValue(new ApiError(409, 'Ese flujo ya está confirmado', 'date'));
    renderPanel();
    await loaded();
    const before = vi.mocked(getCashflows).mock.calls.length;

    fireEvent.click(within(flowRow('2026-11-03', 1)).getByRole('button', { name: 'Confirmar liquidación' }));
    fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Confirmar' }));

    const alert = await within(screen.getByRole('form')).findByRole('alert');
    expect(alert.textContent).toBe('Ese flujo ya está confirmado');
    expect(vi.mocked(getCashflows).mock.calls.length).toBe(before);
    // Sigue editable: se puede corregir y reintentar.
    expect((within(screen.getByRole('form')).getByRole('button', { name: 'Confirmar' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('un monto que no es número no llega al backend', async () => {
    renderPanel();
    await loaded();

    fireEvent.click(within(flowRow('2026-11-03', 1)).getByRole('button', { name: 'Confirmar liquidación' }));
    const form = within(screen.getByRole('form'));
    fireEvent.change(form.getByLabelText('Monto liquidado por el banco'), { target: { value: 'abc' } });
    fireEvent.click(form.getByRole('button', { name: 'Confirmar' }));

    expect((await form.findByRole('alert')).textContent).toBe('El monto debe ser un número.');
    expect(confirmSettlement).not.toHaveBeenCalled();
  });

  it('Cancelar cierra el formulario sin llamar al backend', async () => {
    renderPanel();
    await loaded();

    fireEvent.click(within(flowRow('2026-11-03', 1)).getByRole('button', { name: 'Confirmar liquidación' }));
    fireEvent.click(within(screen.getByRole('form')).getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('form')).toBeNull();
    expect(confirmSettlement).not.toHaveBeenCalled();
  });

  it('el enlace Exportar CSV apunta a cashflowsCsvUrl con los filtros activos', async () => {
    renderPanel();
    await loaded();

    const link = screen.getByRole('link', { name: 'Exportar CSV' });
    expect(link.getAttribute('href')).toBe('/api/cashflows?snapshot=MX-DEMO&format=csv');
    expect(link.hasAttribute('download')).toBe(true);
    expect(cashflowsCsvUrl).toHaveBeenLastCalledWith({ snapshot: 'MX-DEMO', from: '2026-08-12' });
  });

  it('sin filas dice que no hay flujos y un fallo de la API se muestra como aviso', async () => {
    vi.mocked(getCashflows).mockResolvedValueOnce({
      ...RESPONSE,
      rows: [],
      errors: [],
      warnings: [],
      totals: { amount_mxn: 0, by_date: [], by_counterparty: [], by_currency: [] },
    });
    renderPanel();
    expect(await screen.findByText('Sin flujos con esos filtros.')).toBeTruthy();

    vi.mocked(getCashflows).mockRejectedValueOnce(new ApiError(404, 'Snapshot inexistente', 'snapshot'));
    fireEvent.change(screen.getByLabelText('Moneda'), { target: { value: 'USD' } });
    expect((await screen.findByRole('alert')).textContent).toBe('Snapshot inexistente');
  });

  it('espera al as_of del snapshot activo antes de consultar', async () => {
    snapshotState.snapshot = null;
    renderPanel();
    expect(screen.getByText('Cargando snapshot…')).toBeTruthy();
    expect(getCashflows).not.toHaveBeenCalled();
  });
});
