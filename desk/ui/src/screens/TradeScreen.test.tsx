import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  FlowsResponse,
  Snapshot,
  TradeDetail,
  TradeEvent,
  TradeState,
  TradeStatus,
} from '../api/types';
import { ApiError } from '../api/client';
import { SnapshotProvider } from '../state/SnapshotContext';
import TradeScreen from './TradeScreen';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  getTrade: vi.fn(),
  tradeState: vi.fn(),
  tradeFlows: vi.fn(),
  postEvent: vi.fn(),
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    getTrade: mocks.getTrade,
    tradeState: mocks.tradeState,
    tradeFlows: mocks.tradeFlows,
    postEvent: mocks.postEvent,
  };
});

function ev(id: number, type: TradeEvent['type'], event_date: string, data = {}): TradeEvent {
  return { id, trade_id: 1, type, event_date, data, prev_event_id: id > 1 ? id - 1 : null, created_at: '2026-11-10T10:00:00' };
}

const EVENTS: TradeEvent[] = [
  ev(1, 'execution', '2026-11-10'),
  ev(2, 'quantity_change', '2026-12-01', { notional: 60000000 }),
  ev(3, 'termination', '2027-01-15', { amount: 250000 }),
  ev(4, 'transfer', '2027-01-15', { amount: 250000, currency: 'MXN', cause_event_id: 3 }),
];

const TRADE: TradeDetail = {
  id: 1,
  product: 'irs',
  counterparty: 'Banco Alfa',
  trade_date: '2026-11-10',
  start_date: '2026-11-10',
  maturity_date: '2027-11-09',
  params: {},
  notional: 100000000,
  currency: 'MXN',
  maturity: '2027-11-09',
  created_at: '2026-11-10T10:00:00',
  events: EVENTS,
};

function stateOf(status: TradeStatus): TradeState {
  return { id: 1, date: '2026-11-10', status, notional: 100000000, terms: {} };
}

const FLOWS: FlowsResponse = {
  id: 1,
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  flows: [
    { date: '2026-12-08', kind: 'coupon', status: 'projected', amount: 123456.5, currency: 'MXN', df: 0.9912, pv: 122369.4 },
    { date: '2026-11-10', kind: 'coupon', status: 'settled', amount: 99000, currency: 'MXN', df: null, pv: null },
  ],
  warnings: [
    {
      code: 'missing_fixing',
      index: 'TIIE-F',
      dates: ['2026-11-03'],
      message: 'Falta la fijación de TIIE-F; se usó la última publicada',
    },
  ],
};

// Sin terminación ni ejercicio: la operación admite acciones mientras esté viva.
const LIVE_EVENTS = EVENTS.slice(0, 2);

function setup(status: TradeStatus = 'viva', events: TradeEvent[] = LIVE_EVENTS) {
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(
    async (id: string) => ({ id, as_of: '2026-11-10' }) as unknown as Snapshot,
  );
  mocks.getTrade.mockResolvedValue({ ...TRADE, events });
  mocks.tradeState.mockResolvedValue(stateOf(status));
  mocks.tradeFlows.mockResolvedValue(FLOWS);
  mocks.postEvent.mockResolvedValue([]);
}

function renderScreen() {
  return render(
    <SnapshotProvider>
      <MemoryRouter initialEntries={['/portafolio/1']}>
        <Routes>
          <Route path="/portafolio/:id" element={<TradeScreen />} />
          <Route path="/portafolio" element={<div>lista</div>} />
        </Routes>
      </MemoryRouter>
    </SnapshotProvider>,
  );
}

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('TradeScreen', () => {
  it('carga la operación, el estado a la fecha del snapshot y los flujos', async () => {
    setup();
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(mocks.getTrade).toHaveBeenCalledWith(1);
    expect(mocks.tradeState).toHaveBeenCalledWith(1, '2026-11-10');
    expect(mocks.tradeFlows).toHaveBeenCalledWith(1, 'MX-DEMO');
    expect(screen.getByText('Viva')).toBeTruthy();
    expect(screen.getByText('MXN 100,000,000.00')).toBeTruthy();
    expect(screen.getByText('Swap de tasas (IRS)')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Volver al portafolio' })).toBeTruthy();
  });

  it('lista los eventos de la línea de tiempo en orden de fecha', async () => {
    setup();
    // El backend ya los ordena; aquí llegan desordenados para comprobar el orden mostrado.
    mocks.getTrade.mockResolvedValue({ ...TRADE, events: [EVENTS[2], EVENTS[0], EVENTS[3], EVENTS[1]] });
    renderScreen();
    const items = (await screen.findAllByRole('listitem')).filter((li) =>
      li.classList.contains('trade__event'),
    );
    expect(items.map((li) => li.textContent)).toEqual([
      '2026-11-10Pactada',
      '2026-12-01Cambio de nocionalNuevo nocional 60,000,000.00',
      '2027-01-15Terminación anticipadaImporte MXN 250,000.00',
      '2027-01-15TransferenciaImporte MXN 250,000.00',
    ]);
  });

  it('rotula distinto un flujo liquidado y uno proyectado, y muestra los avisos', async () => {
    setup();
    renderScreen();
    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    // Ordenados por fecha: primero el liquidado.
    expect(rows[0].textContent).toContain('Liquidado');
    expect(rows[0].classList.contains('trade__flow--settled')).toBe(true);
    expect(rows[0].textContent).toContain('—');
    expect(rows[1].textContent).toContain('Proyectado');
    expect(rows[1].classList.contains('trade__flow--projected')).toBe(true);
    expect(rows[1].textContent).toContain('0.991200');
    expect(rows[1].textContent).toContain('122,369.40');
    const warnings = screen.getByRole('list', { name: 'Avisos' });
    expect(warnings.textContent).toContain('Falta la fijación de TIIE-F');
    expect(warnings.textContent).toContain('2026-11-03');
  });

  it('el encabezado de Fecha del calendario se alinea como sus celdas (a la derecha)', async () => {
    setup();
    renderScreen();
    const table = await screen.findByRole('table');
    expect(within(table).getByRole('columnheader', { name: 'Fecha' }).classList.contains('num')).toBe(true);
    const firstDate = within(table).getAllByRole('row')[1].querySelector('td');
    expect(firstDate?.classList.contains('num')).toBe(true);
  });

  it('Terminar anticipadamente llama postEvent con la fecha y el importe y recarga', async () => {
    setup();
    renderScreen();
    await screen.findByText('Banco Alfa');
    const form = screen.getByRole('form', { name: 'Terminar anticipadamente' });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2026-11-20' } });
    fireEvent.change(within(form).getByLabelText('Importe (MXN)'), { target: { value: '1,250,000.5' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Terminar anticipadamente' }));

    await waitFor(() =>
      expect(mocks.postEvent).toHaveBeenCalledWith(1, {
        type: 'termination',
        event_date: '2026-11-20',
        data: { amount: 1250000.5 },
      }),
    );
    await waitFor(() => expect(mocks.getTrade).toHaveBeenCalledTimes(2));
    expect(mocks.tradeState).toHaveBeenCalledTimes(2);
    expect(mocks.tradeFlows).toHaveBeenCalledTimes(2);
  });

  it('Cambiar nocional llama postEvent con quantity_change', async () => {
    setup();
    renderScreen();
    await screen.findByText('Banco Alfa');
    const form = screen.getByRole('form', { name: 'Cambiar nocional' });
    fireEvent.change(within(form).getByLabelText('Nuevo nocional'), { target: { value: '60000000' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Cambiar nocional' }));
    await waitFor(() =>
      expect(mocks.postEvent).toHaveBeenCalledWith(1, {
        type: 'quantity_change',
        event_date: '2026-11-10',
        data: { notional: 60000000 },
      }),
    );
  });

  it('muestra el error del campo bajo el input y el 409 como banner', async () => {
    setup();
    renderScreen();
    await screen.findByText('Banco Alfa');
    const form = screen.getByRole('form', { name: 'Terminar anticipadamente' });
    const amount = within(form).getByLabelText('Importe (MXN)');
    fireEvent.change(amount, { target: { value: '10' } });

    mocks.postEvent.mockRejectedValueOnce(new ApiError(400, 'La fecha es anterior a la pactada', 'event_date'));
    fireEvent.click(within(form).getByRole('button', { name: 'Terminar anticipadamente' }));
    const fieldError = await within(form).findByText('La fecha es anterior a la pactada');
    expect(fieldError.getAttribute('role')).toBe('alert');
    expect(within(form).getByLabelText('Fecha').getAttribute('aria-invalid')).toBe('true');

    mocks.postEvent.mockRejectedValueOnce(new ApiError(409, 'La operación ya no está viva en esa fecha', 'id'));
    fireEvent.click(within(form).getByRole('button', { name: 'Terminar anticipadamente' }));
    const banner = await screen.findByText('La operación ya no está viva en esa fecha');
    expect(form.contains(banner)).toBe(false);
  });

  it('con estado terminada no hay botones de acción y una línea dice cuándo se terminó', async () => {
    setup('terminada', EVENTS);
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(screen.queryByRole('button', { name: 'Terminar anticipadamente' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Cambiar nocional' })).toBeNull();
    const actions = screen.getByRole('region', { name: 'Acciones' });
    expect(actions.textContent).toBe('AccionesTerminada el 2027-01-15');
  });

  it('una terminación registrada en una fecha posterior a la de la ficha también cierra las acciones', async () => {
    setup('viva', EVENTS); // la ficha está a 2026-11-10 y la terminación es del 2027-01-15
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(screen.queryByRole('form', { name: 'Terminar anticipadamente' })).toBeNull();
    expect(screen.queryByRole('form', { name: 'Cambiar nocional' })).toBeNull();
    expect(screen.getByRole('region', { name: 'Acciones' }).textContent).toBe('AccionesTerminada el 2027-01-15');
  });

  it('una opción ejercida dice "Ejercida el" con la fecha del ejercicio', async () => {
    setup('ejercida', [ev(1, 'execution', '2026-11-10'), ev(2, 'exercise', '2026-12-05', { amount: 4000 })]);
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(screen.getByRole('region', { name: 'Acciones' }).textContent).toBe('AccionesEjercida el 2026-12-05');
    expect(screen.queryByRole('form')).toBeNull();
  });

  it('una operación vencida sin terminación ni ejercicio no deja un encabezado Acciones vacío', async () => {
    setup('vencida');
    renderScreen();
    await screen.findByText('Banco Alfa');
    expect(screen.queryByRole('region', { name: 'Acciones' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Acciones' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Línea de tiempo' })).toBeTruthy();
  });

  it('con estado no_pactada avisa y no ofrece acciones', async () => {
    setup('no_pactada');
    renderScreen();
    await screen.findByText('No pactada a esta fecha');
    expect(screen.getByRole('heading', { name: 'Acciones' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Terminar anticipadamente' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Cambiar nocional' })).toBeNull();
  });

  it('un 404 de la operación se muestra como error', async () => {
    setup();
    mocks.getTrade.mockRejectedValue(new ApiError(404, 'Operación inexistente', 'id'));
    renderScreen();
    expect(await screen.findByText('Operación inexistente')).toBeTruthy();
  });
});
