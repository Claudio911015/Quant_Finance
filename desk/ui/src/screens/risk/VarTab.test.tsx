import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { HistVarResponse } from '../../api/riskTypes';
import type { Snapshot, VarResponse } from '../../api/types';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { VarTab } from './VarTab';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  riskVar: vi.fn(),
  riskVarHistorical: vi.fn(),
}));

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    riskVar: mocks.riskVar,
  };
});

vi.mock('../../api/riskClient', () => ({ riskVarHistorical: mocks.riskVarHistorical }));

const PARAMETRIC: VarResponse = {
  snapshot: 'MX-DEMO',
  var_mxn: 1000000,
  horizon_days: 10,
  confidence: 0.99,
  factors: [
    { factor: 'TIIE-F', unit: 'bp', exposure_mxn: 1000, daily_vol: 4, var_mxn: 700 },
    { factor: 'SOFR', unit: 'bp', exposure_mxn: 400, daily_vol: 5, var_mxn: 300 },
    { factor: 'USDMXN', unit: 'ret', exposure_mxn: 200000, daily_vol: 0.0075, var_mxn: 900 },
  ],
  errors: [],
};

const HISTORICAL: HistVarResponse = {
  snapshot: 'MX-DEMO',
  method: 'historical',
  var_mxn: 1250000,
  es_mxn: 1500000.5,
  horizon_days: 10,
  confidence: 0.99,
  window_days: 250,
  worst_day: { date: '2026-03-12', pnl_mxn: -345678.9 },
  history: {
    source: 'synthetic',
    label: 'Sintético (semilla fija, vols y correlaciones de MX-DEMO)',
    from: '2025-11-13',
    to: '2026-11-09',
    observations: 250,
    by_source: { synthetic: 750 },
  },
  factors: [
    { factor: 'TIIE-F', unit: 'bp', exposure_mxn: -1000 },
    { factor: 'SOFR', unit: 'bp', exposure_mxn: -400 },
    { factor: 'USDMXN', unit: 'ret', exposure_mxn: 200000 },
  ],
  errors: [],
};

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderTab() {
  return render(
    <SnapshotProvider>
      <SwitchTo id="OTRO" />
      <VarTab />
    </SnapshotProvider>,
  );
}

const parametricCard = () => screen.getByRole('region', { name: 'Paramétrico' });
const historicalCard = () => screen.getByRole('region', { name: 'Histórico' });

beforeEach(() => {
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.riskVar.mockImplementation(async (id: string) => ({ ...PARAMETRIC, snapshot: id }));
  mocks.riskVarHistorical.mockImplementation(async (id: string) => ({ ...HISTORICAL, snapshot: id }));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('VarTab: dos tarjetas lado a lado', () => {
  it('muestra el VaR paramétrico con su tabla por factor', async () => {
    renderTab();
    const card = parametricCard();

    expect(await within(card).findByText('MXN 1,000,000.00')).toBeTruthy();
    expect(within(card).getByText('VaR 99 % a 10 días')).toBeTruthy();
    for (const f of ['TIIE-F', 'SOFR', 'USDMXN']) {
      expect(within(card).getByRole('cell', { name: f })).toBeTruthy();
    }
    expect(within(card).getByText('4.00 pb')).toBeTruthy();
    expect(within(card).getByText('0.7500 %')).toBeTruthy();
    expect(within(card).getByText('200,000.00')).toBeTruthy();
    expect(mocks.riskVar).toHaveBeenCalledWith('MX-DEMO', 10, 0.99);
  });

  it('muestra el VaR histórico, el ES, el peor día y la historia usada', async () => {
    renderTab();
    const card = historicalCard();

    expect(await within(card).findByText('MXN 1,250,000.00')).toBeTruthy();
    expect(within(card).getByText('MXN 1,500,000.50')).toBeTruthy();
    expect(within(card).getByText('Déficit esperado (ES)')).toBeTruthy();
    // Peor día: fecha y P&L sin escalar.
    expect(within(card).getByText('2026-03-12')).toBeTruthy();
    expect(within(card).getByText('MXN -345,678.90')).toBeTruthy();
    // Historia usada: fuente, descripción, rango y observaciones.
    expect(within(card).getByText('Historia usada')).toBeTruthy();
    expect(within(card).getByText('Sintética')).toBeTruthy();
    expect(within(card).getByText('Sintético (semilla fija, vols y correlaciones de MX-DEMO)')).toBeTruthy();
    expect(within(card).getByText('2025-11-13 – 2026-11-09')).toBeTruthy();
    expect(within(card).getByText('250')).toBeTruthy();
    expect(within(card).getByText('-1,000.00')).toBeTruthy();
    expect(mocks.riskVarHistorical).toHaveBeenCalledWith('MX-DEMO', {
      horizon_days: 10,
      confidence: 0.99,
      window_days: 250,
    });
  });

  it('muestra la diferencia Histórico − Paramétrico en MXN y en %', async () => {
    renderTab();
    await within(historicalCard()).findByText('MXN 1,250,000.00');

    const diff = screen.getByRole('region', { name: 'Diferencia' });
    expect(within(diff).getByText('Histórico − Paramétrico')).toBeTruthy();
    expect(within(diff).getByText('MXN +250,000.00 (+25.00 %)')).toBeTruthy();
  });

  it('la diferencia negativa lleva su signo y no se muestra sin una de las dos', async () => {
    mocks.riskVarHistorical.mockResolvedValueOnce({ ...HISTORICAL, var_mxn: 800000 });
    renderTab();
    const diff = await screen.findByRole('region', { name: 'Diferencia' });
    expect(within(diff).getByText('MXN -200,000.00 (-20.00 %)')).toBeTruthy();

    mocks.riskVarHistorical.mockRejectedValueOnce(new ApiError(409, 'Historia insuficiente', 'window_days'));
    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Diferencia' })).toBeNull());
  });
});

describe('VarTab: entradas y botón Calcular', () => {
  it('los tres campos arrancan en 10, 99 y 250', async () => {
    renderTab();
    await within(parametricCard()).findByText('MXN 1,000,000.00');

    expect((screen.getByLabelText('Horizonte (días)') as HTMLInputElement).value).toBe('10');
    expect((screen.getByLabelText('Confianza (%)') as HTMLInputElement).value).toBe('99');
    expect((screen.getByLabelText('Ventana (días)') as HTMLInputElement).value).toBe('250');
  });

  it('cambiar un campo no calcula hasta pulsar Calcular; entonces manda ambas llamadas', async () => {
    renderTab();
    await within(parametricCard()).findByText('MXN 1,000,000.00');
    expect(mocks.riskVar).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByLabelText('Horizonte (días)'), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText('Confianza (%)'), { target: { value: '95' } });
    fireEvent.change(screen.getByLabelText('Ventana (días)'), { target: { value: '120' } });
    expect(mocks.riskVar).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));

    await waitFor(() => expect(mocks.riskVar).toHaveBeenLastCalledWith('MX-DEMO', 5, 0.95));
    expect(mocks.riskVarHistorical).toHaveBeenLastCalledWith('MX-DEMO', {
      horizon_days: 5,
      confidence: 0.95,
      window_days: 120,
    });
  });

  it('un 400 con field window_days aparece bajo su campo y la tarjeta paramétrica sigue visible', async () => {
    renderTab();
    await within(parametricCard()).findByText('MXN 1,000,000.00');
    mocks.riskVarHistorical.mockRejectedValueOnce(
      new ApiError(400, 'La ventana debe ser al menos 60 días', 'window_days'),
    );

    fireEvent.change(screen.getByLabelText('Ventana (días)'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));

    const message = await screen.findByText('La ventana debe ser al menos 60 días');
    expect(message.id).toBe('vartab-window-error');
    const input = screen.getByLabelText('Ventana (días)');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('vartab-window-error');
    expect(within(parametricCard()).getByText('MXN 1,000,000.00')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('un campo que no es número se marca sin llamar a la API', async () => {
    renderTab();
    await within(parametricCard()).findByText('MXN 1,000,000.00');
    mocks.riskVar.mockClear();
    mocks.riskVarHistorical.mockClear();

    fireEvent.change(screen.getByLabelText('Horizonte (días)'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));

    expect(await screen.findByText('Ingresa un número válido')).toBeTruthy();
    expect(mocks.riskVar).not.toHaveBeenCalled();
    expect(mocks.riskVarHistorical).not.toHaveBeenCalled();
  });
});

describe('VarTab: historia insuficiente (409)', () => {
  it('el aviso queda solo en la tarjeta histórica y la paramétrica sigue visible', async () => {
    const message = 'Historia insuficiente: hay 40 días con los tres factores hasta el 2026-11-09 (se piden 250)';
    mocks.riskVarHistorical.mockRejectedValue(new ApiError(409, message, 'window_days'));
    renderTab();

    const note = await within(historicalCard()).findByRole('status');
    expect(note.textContent).toBe(message);
    expect(note.className).toContain('radv-note--warn');
    // La paramétrica sigue con sus cifras y sin avisos.
    expect(await within(parametricCard()).findByText('MXN 1,000,000.00')).toBeTruthy();
    expect(within(parametricCard()).queryByRole('status')).toBeNull();
    expect(within(historicalCard()).queryByRole('alert')).toBeNull();
    // El 409 es un aviso, no un error del campo: no se repite bajo la ventana.
    expect(screen.getByLabelText('Ventana (días)').getAttribute('aria-invalid')).toBeNull();
  });

  it('un fallo de red en la histórica es una alerta de esa tarjeta', async () => {
    mocks.riskVarHistorical.mockRejectedValue(new Error('network'));
    renderTab();

    const alert = await within(historicalCard()).findByRole('alert');
    expect(alert.textContent).toBe('No se pudo conectar con el backend');
    expect(await within(parametricCard()).findByText('MXN 1,000,000.00')).toBeTruthy();
  });
});

describe('VarTab: cambio de snapshot', () => {
  it('recalcula ambos métodos con el snapshot nuevo y los valores ya calculados', async () => {
    renderTab();
    await within(parametricCard()).findByText('MXN 1,000,000.00');
    // Un valor tecleado pero sin calcular no se aplica al cambiar de snapshot.
    fireEvent.change(screen.getByLabelText('Horizonte (días)'), { target: { value: '3' } });

    fireEvent.click(screen.getByRole('button', { name: 'cambiar a OTRO' }));

    await waitFor(() => {
      expect(mocks.riskVar).toHaveBeenLastCalledWith('OTRO', 10, 0.99);
      expect(mocks.riskVarHistorical).toHaveBeenLastCalledWith('OTRO', {
        horizon_days: 10,
        confidence: 0.99,
        window_days: 250,
      });
    });
  });
});
