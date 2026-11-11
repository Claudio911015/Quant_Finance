import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { Snapshot, Trade } from '../../api/types';
import type { Limit, LimitBreach, LimitCheckResponse, LimitUsage, LimitUsageResponse } from '../../api/riskTypes';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { LimitsTab } from './LimitsTab';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  listTrades: vi.fn(),
  limitUsage: vi.fn(),
  checkLimits: vi.fn(),
  createLimit: vi.fn(),
  addLimitEvent: vi.fn(),
  listBreaches: vi.fn(),
}));

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    listTrades: mocks.listTrades,
  };
});

vi.mock('../../api/riskClient', () => ({
  limitUsage: mocks.limitUsage,
  checkLimits: mocks.checkLimits,
  createLimit: mocks.createLimit,
  addLimitEvent: mocks.addLimitEvent,
  listBreaches: mocks.listBreaches,
}));

function trade(id: number, counterparty: string): Trade {
  return {
    id,
    product: 'irs',
    counterparty,
    trade_date: '2026-11-10',
    start_date: '2026-11-10',
    maturity_date: '2027-11-10',
    params: {},
    notional: 1e6,
    currency: 'MXN',
    maturity: '2027-11-10',
    created_at: '2026-11-10',
  };
}

// Dos operaciones de Banco B y una de Banco A: los nombres únicos salen ordenados.
const TRADES = [trade(1, 'Banco B'), trade(2, 'Banco A'), trade(3, 'Banco B')];

const ROWS: LimitUsage[] = [
  { limit_id: 1, scope: 'counterparty', key: 'Banco A', metric: 'pv_exposure', amount: 50e6, usage: 10e6, pct: 20, status: 'ok' },
  { limit_id: 2, scope: 'factor', key: 'TIIE-F', metric: 'dv01', amount: 100000, usage: 82000, pct: 82, status: 'alerta' },
  { limit_id: 3, scope: 'factor', key: 'USDMXN', metric: 'fx_delta', amount: 1e6, usage: 1.52e6, pct: 152, status: 'exceso' },
  { limit_id: 4, scope: 'portfolio', key: 'portfolio', metric: 'var', amount: 2e6, usage: 1e6, pct: 50, status: 'ok' },
];

function usageFor(snapshot: string, usage: LimitUsage[] = ROWS): LimitUsageResponse {
  return {
    snapshot,
    as_of: '2026-11-10',
    thresholds: { alert_pct: 80, breach_pct: 100 },
    usage,
    errors: [],
  };
}

const BREACH: LimitBreach = {
  id: 7,
  limit_id: 3,
  scope: 'factor',
  key: 'USDMXN',
  metric: 'fx_delta',
  snapshot: 'MX-DEMO',
  as_of: '2026-11-09',
  amount: 1e6,
  usage: 1.52e6,
  pct: 152,
  created_at: '2026-11-10T18:00:00+00:00',
};

const LIMIT: Limit = {
  id: 9,
  scope: 'counterparty',
  key: 'Banco A',
  metric: 'pv_exposure',
  amount: 5e7,
  status: 'activo',
  created_at: '2026-11-10T18:00:00+00:00',
  events: [],
};

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderTab() {
  return render(
    <SnapshotProvider>
      <SwitchTo id="OTRO" />
      <LimitsTab />
    </SnapshotProvider>,
  );
}

const usageCard = () => screen.getByRole('region', { name: 'Uso de límites' });
const formCard = () => screen.getByRole('region', { name: 'Nuevo límite' });
const logCard = () => screen.getByRole('region', { name: 'Bitácora de excesos' });

/** Fila de la tabla de uso que contiene el texto dado en su columna de clave. */
function usageRow(key: string): HTMLElement {
  const cell = within(usageCard()).getByRole('cell', { name: key });
  return cell.closest('tr') as HTMLElement;
}

beforeEach(() => {
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.listTrades.mockResolvedValue(TRADES);
  mocks.limitUsage.mockImplementation(async (id: string) => usageFor(id));
  mocks.listBreaches.mockResolvedValue([BREACH]);
  mocks.createLimit.mockResolvedValue(LIMIT);
  mocks.addLimitEvent.mockResolvedValue(LIMIT);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('LimitsTab: uso de límites', () => {
  it('muestra cada estado con su texto y data-status, y la barra con tope visual de 100 %', async () => {
    renderTab();
    // Dos filas en límite: ambas con su texto y data-status.
    const enLimite = await within(usageCard()).findAllByText('En límite');
    expect(enLimite).toHaveLength(2);
    expect(enLimite.every((el) => el.getAttribute('data-status') === 'ok')).toBe(true);
    expect(mocks.limitUsage).toHaveBeenCalledWith('MX-DEMO');

    const alerta = within(usageRow('TIIE-F')).getByText('Alerta');
    expect(alerta.getAttribute('data-status')).toBe('alerta');
    const exceso = within(usageRow('USDMXN')).getByText('Exceso');
    expect(exceso.getAttribute('data-status')).toBe('exceso');

    // El texto lleva el % real; el relleno de la barra se corta en 100.
    expect(within(usageRow('USDMXN')).getByText('152.0 %')).toBeTruthy();
    const bar = usageRow('USDMXN').querySelector('.radv-bar') as HTMLElement;
    expect(bar.getAttribute('data-status')).toBe('exceso');
    expect(bar.style.getPropertyValue('--pct')).toBe('100');
    const barAlerta = usageRow('TIIE-F').querySelector('.radv-bar') as HTMLElement;
    expect(barAlerta.style.getPropertyValue('--pct')).toBe('82');

    // Alcance, métrica y montos en MXN; el portafolio no lleva clave.
    const row = usageRow('TIIE-F');
    expect(within(row).getByText('Factor')).toBeTruthy();
    expect(within(row).getByText('DV01 por curva')).toBeTruthy();
    expect(within(row).getByText('MXN 100,000.00')).toBeTruthy();
    expect(within(row).getByText('MXN 82,000.00')).toBeTruthy();
    expect(within(usageCard()).queryByText('portfolio')).toBeNull();
  });

  it('sin límites vigentes lo dice', async () => {
    mocks.limitUsage.mockImplementation(async (id: string) => usageFor(id, []));
    renderTab();
    expect(await within(usageCard()).findByText('Sin límites vigentes.')).toBeTruthy();
  });

  it('las operaciones excluidas del cálculo se avisan', async () => {
    mocks.limitUsage.mockImplementation(async (id: string) => ({
      ...usageFor(id),
      errors: [{ id: 5, error: 'Sin cotización' }],
    }));
    renderTab();
    const note = await within(usageCard()).findByRole('status');
    expect(note.textContent).toContain('#5 (Sin cotización)');
  });

  it('recalcula al cambiar de snapshot', async () => {
    renderTab();
    await within(usageCard()).findByText('Alerta');

    fireEvent.click(screen.getByText('cambiar a OTRO'));

    await waitFor(() => expect(mocks.limitUsage).toHaveBeenLastCalledWith('OTRO'));
  });

  it('un error del backend al calcular el uso se muestra', async () => {
    mocks.limitUsage.mockRejectedValue(new ApiError(404, 'No existe el snapshot', 'snapshot'));
    renderTab();
    expect((await within(usageCard()).findByRole('alert')).textContent).toBe('No existe el snapshot');
  });
});

describe('LimitsTab: cambio de monto y baja', () => {
  it('Cambiar monto manda un evento change con el monto nuevo y refresca', async () => {
    renderTab();
    await within(usageCard()).findByText('Alerta');
    const calls = mocks.limitUsage.mock.calls.length;

    fireEvent.click(within(usageRow('TIIE-F')).getByRole('button', { name: 'Cambiar monto' }));
    const input = within(usageRow('TIIE-F')).getByLabelText('Nuevo monto (MXN)') as HTMLInputElement;
    expect(input.value).toBe('100000');
    fireEvent.change(input, { target: { value: '150000' } });
    fireEvent.click(within(usageRow('TIIE-F')).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(mocks.addLimitEvent).toHaveBeenCalledWith(2, { type: 'change', amount: 150000 }));
    await waitFor(() => expect(mocks.limitUsage.mock.calls.length).toBe(calls + 1));
  });

  it('un monto inválido en el cambio no llama al backend', async () => {
    renderTab();
    await within(usageCard()).findByText('Alerta');

    fireEvent.click(within(usageRow('TIIE-F')).getByRole('button', { name: 'Cambiar monto' }));
    fireEvent.change(within(usageRow('TIIE-F')).getByLabelText('Nuevo monto (MXN)'), { target: { value: '' } });
    fireEvent.click(within(usageRow('TIIE-F')).getByRole('button', { name: 'Guardar' }));

    expect(within(usageRow('TIIE-F')).getByText('Ingresa un número válido')).toBeTruthy();
    expect(mocks.addLimitEvent).not.toHaveBeenCalled();
  });

  it('el error del backend al cambiar el monto aparece en la fila', async () => {
    mocks.addLimitEvent.mockRejectedValueOnce(new ApiError(400, 'El monto debe ser mayor que 0', 'amount'));
    renderTab();
    await within(usageCard()).findByText('Alerta');

    fireEvent.click(within(usageRow('TIIE-F')).getByRole('button', { name: 'Cambiar monto' }));
    fireEvent.change(within(usageRow('TIIE-F')).getByLabelText('Nuevo monto (MXN)'), { target: { value: '-1' } });
    fireEvent.click(within(usageRow('TIIE-F')).getByRole('button', { name: 'Guardar' }));

    expect(await within(usageRow('TIIE-F')).findByText('El monto debe ser mayor que 0')).toBeTruthy();
  });

  it('Dar de baja pide confirmación y manda un evento retire', async () => {
    renderTab();
    await within(usageCard()).findByText('Alerta');
    const calls = mocks.limitUsage.mock.calls.length;

    fireEvent.click(within(usageRow('Banco A')).getByRole('button', { name: 'Dar de baja' }));
    expect(mocks.addLimitEvent).not.toHaveBeenCalled();
    expect(within(usageRow('Banco A')).getByText('¿Dar de baja este límite?')).toBeTruthy();
    fireEvent.click(within(usageRow('Banco A')).getByRole('button', { name: 'Confirmar baja' }));

    await waitFor(() => expect(mocks.addLimitEvent).toHaveBeenCalledWith(1, { type: 'retire' }));
    await waitFor(() => expect(mocks.limitUsage.mock.calls.length).toBe(calls + 1));
  });

  it('cancelar la baja no llama al backend', async () => {
    renderTab();
    await within(usageCard()).findByText('Alerta');

    fireEvent.click(within(usageRow('Banco A')).getByRole('button', { name: 'Dar de baja' }));
    fireEvent.click(within(usageRow('Banco A')).getByRole('button', { name: 'Cancelar' }));

    expect(mocks.addLimitEvent).not.toHaveBeenCalled();
    expect(within(usageRow('Banco A')).getByRole('button', { name: 'Dar de baja' })).toBeTruthy();
  });
});

describe('LimitsTab: alta de límites', () => {
  const metricOptions = () =>
    within(screen.getByLabelText('Métrica')).getAllByRole('option').map((o) => o.textContent);
  const keyOptions = () => within(screen.getByLabelText('Clave')).getAllByRole('option').map((o) => o.textContent);

  it('las métricas se filtran por alcance y la clave sigue a la métrica', async () => {
    renderTab();
    await within(formCard()).findByLabelText('Clave');

    // Contraparte: una métrica y los nombres únicos de las operaciones, ordenados.
    expect(metricOptions()).toEqual(['Exposición (PV positivo neto)']);
    await waitFor(() => expect(keyOptions()).toEqual(['Banco A', 'Banco B']));

    // Factor: DV01 (curvas) y delta USDMXN.
    fireEvent.change(screen.getByLabelText('Alcance'), { target: { value: 'factor' } });
    expect(metricOptions()).toEqual(['DV01 por curva', 'Delta USDMXN (MXN por 1 %)']);
    expect(keyOptions()).toEqual(['TIIE-F', 'SOFR']);
    fireEvent.change(screen.getByLabelText('Métrica'), { target: { value: 'fx_delta' } });
    expect(keyOptions()).toEqual(['USDMXN']);

    // Portafolio: solo VaR y sin Clave.
    fireEvent.change(screen.getByLabelText('Alcance'), { target: { value: 'portfolio' } });
    expect(metricOptions()).toEqual(['VaR paramétrico 1 día 99 %']);
    expect(screen.queryByLabelText('Clave')).toBeNull();
  });

  it('el alta de contraparte manda el cuerpo correcto y refresca el uso', async () => {
    renderTab();
    await waitFor(() => expect(keyOptions()).toEqual(['Banco A', 'Banco B']));
    const calls = mocks.limitUsage.mock.calls.length;

    fireEvent.change(screen.getByLabelText('Clave'), { target: { value: 'Banco B' } });
    fireEvent.change(screen.getByLabelText('Monto (MXN)'), { target: { value: '50000000' } });
    fireEvent.change(screen.getByLabelText('Motivo'), { target: { value: ' Política 2026 ' } });
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar límite' }));

    await waitFor(() =>
      expect(mocks.createLimit).toHaveBeenCalledWith({
        scope: 'counterparty',
        key: 'Banco B',
        metric: 'pv_exposure',
        amount: 5e7,
        reason: 'Política 2026',
      }),
    );
    await waitFor(() => expect(mocks.limitUsage.mock.calls.length).toBe(calls + 1));
    expect((screen.getByLabelText('Monto (MXN)') as HTMLInputElement).value).toBe('');
  });

  it('el alta de portafolio no manda clave ni motivo vacío', async () => {
    renderTab();
    await within(formCard()).findByLabelText('Clave');

    fireEvent.change(screen.getByLabelText('Alcance'), { target: { value: 'portfolio' } });
    fireEvent.change(screen.getByLabelText('Monto (MXN)'), { target: { value: '2000000' } });
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar límite' }));

    await waitFor(() =>
      expect(mocks.createLimit).toHaveBeenCalledWith({ scope: 'portfolio', metric: 'var', amount: 2e6 }),
    );
  });

  it('un monto vacío o no numérico se avisa bajo Monto sin llamar al backend', async () => {
    renderTab();
    await within(formCard()).findByLabelText('Clave');

    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar límite' }));

    const input = screen.getByLabelText('Monto (MXN)');
    expect(within(formCard()).getByText('Ingresa un número válido')).toBeTruthy();
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(mocks.createLimit).not.toHaveBeenCalled();
  });

  it('el 409 de key aparece bajo Clave', async () => {
    mocks.createLimit.mockRejectedValueOnce(new ApiError(409, 'Ya hay un límite activo para esa clave', 'key'));
    renderTab();
    await waitFor(() => expect(keyOptions()).toEqual(['Banco A', 'Banco B']));

    fireEvent.change(screen.getByLabelText('Monto (MXN)'), { target: { value: '1000' } });
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar límite' }));

    const message = await within(formCard()).findByText('Ya hay un límite activo para esa clave');
    const select = screen.getByLabelText('Clave');
    expect(select.getAttribute('aria-invalid')).toBe('true');
    expect(select.getAttribute('aria-describedby')).toBe(message.id);
    expect(within(formCard()).queryByRole('alert')).toBeNull();
  });

  it('el 400 de amount aparece bajo Monto', async () => {
    mocks.createLimit.mockRejectedValueOnce(new ApiError(400, 'El monto debe ser mayor que 0', 'amount'));
    renderTab();
    await within(formCard()).findByLabelText('Clave');

    fireEvent.change(screen.getByLabelText('Monto (MXN)'), { target: { value: '-5' } });
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar límite' }));

    const message = await within(formCard()).findByText('El monto debe ser mayor que 0');
    expect(screen.getByLabelText('Monto (MXN)').getAttribute('aria-describedby')).toBe(message.id);
  });

  it('un error sin campo del formulario sale como alerta', async () => {
    mocks.createLimit.mockRejectedValueOnce(new ApiError(0, 'No se pudo conectar con el backend'));
    renderTab();
    await within(formCard()).findByLabelText('Clave');

    fireEvent.change(screen.getByLabelText('Monto (MXN)'), { target: { value: '10' } });
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar límite' }));

    expect((await within(formCard()).findByRole('alert')).textContent).toBe('No se pudo conectar con el backend');
  });
});

describe('LimitsTab: revisar límites y bitácora', () => {
  it('Revisar límites muestra los excesos nuevos y refresca la bitácora', async () => {
    const checked: LimitCheckResponse = { ...usageFor('MX-DEMO'), new_breaches: [BREACH] };
    mocks.checkLimits.mockResolvedValue(checked);
    renderTab();
    await within(usageCard()).findByText('Alerta');
    const logCalls = mocks.listBreaches.mock.calls.length;

    fireEvent.click(within(usageCard()).getByRole('button', { name: 'Revisar límites' }));

    const note = await within(usageCard()).findByText(/Excesos nuevos/);
    expect(mocks.checkLimits).toHaveBeenCalledWith('MX-DEMO');
    expect(note.textContent).toContain('Factor · USDMXN · Delta USDMXN (MXN por 1 %)');
    expect(note.textContent).toContain('152.0 %');
    await waitFor(() => expect(mocks.listBreaches.mock.calls.length).toBe(logCalls + 1));
  });

  it('sin excesos nuevos lo dice', async () => {
    mocks.checkLimits.mockResolvedValue({ ...usageFor('MX-DEMO'), new_breaches: [] });
    renderTab();
    await within(usageCard()).findByText('Alerta');

    fireEvent.click(within(usageCard()).getByRole('button', { name: 'Revisar límites' }));

    expect(await within(usageCard()).findByText('Sin excesos nuevos')).toBeTruthy();
  });

  it('un error al revisar se muestra como alerta', async () => {
    mocks.checkLimits.mockRejectedValue(new ApiError(404, 'No existe el snapshot', 'snapshot'));
    renderTab();
    await within(usageCard()).findByText('Alerta');

    fireEvent.click(within(usageCard()).getByRole('button', { name: 'Revisar límites' }));

    expect((await within(usageCard()).findByRole('alert')).textContent).toBe('No existe el snapshot');
  });

  it('la bitácora lista fecha de valuación, snapshot, límite, monto, uso y %', async () => {
    renderTab();
    const card = logCard();
    await within(card).findByText('2026-11-09');

    const row = within(card).getByText('2026-11-09').closest('tr') as HTMLElement;
    expect(within(row).getByText('MX-DEMO')).toBeTruthy();
    expect(within(row).getByText('Factor · USDMXN · Delta USDMXN (MXN por 1 %)')).toBeTruthy();
    expect(within(row).getByText('MXN 1,000,000.00')).toBeTruthy();
    expect(within(row).getByText('MXN 1,520,000.00')).toBeTruthy();
    expect(within(row).getByText('152.0 %')).toBeTruthy();
  });

  it('sin excesos registrados lo dice', async () => {
    mocks.listBreaches.mockResolvedValue([]);
    renderTab();
    expect(await within(logCard()).findByText('Sin excesos registrados.')).toBeTruthy();
  });
});
