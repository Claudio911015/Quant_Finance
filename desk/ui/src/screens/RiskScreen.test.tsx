import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { Dv01Response, ScenariosResponse, Snapshot, Trade, VarResponse } from '../api/types';
import { SnapshotProvider, useSnapshot } from '../state/SnapshotContext';
import { RiskScreen } from './RiskScreen';

const mocks = vi.hoisted(() => ({
  chart: { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() },
  grid: { setGridOption: vi.fn(), destroy: vi.fn() },
  createGrid: vi.fn(),
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  riskDv01: vi.fn(),
  riskScenarios: vi.fn(),
  riskVar: vi.fn(),
  listTrades: vi.fn(),
}));

vi.mock('echarts', () => ({ init: () => mocks.chart }));

vi.mock('ag-grid-community', async (importOriginal) => {
  const actual = await importOriginal<typeof import('ag-grid-community')>();
  mocks.createGrid.mockImplementation(() => mocks.grid);
  return { ...actual, createGrid: mocks.createGrid };
});

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    riskDv01: mocks.riskDv01,
    riskScenarios: mocks.riskScenarios,
    riskVar: mocks.riskVar,
    listTrades: mocks.listTrades,
  };
});

const DV01: Dv01Response = {
  snapshot: 'MX-DEMO',
  total_mxn: -1500,
  parallel_mxn: -1400,
  curves: {
    'TIIE-F': {
      parallel_mxn: -1000,
      points: [
        { label: '13x28', days: 364, dv01_mxn: -400 },
        { label: '26x28', days: 728, dv01_mxn: -600 },
      ],
    },
    SOFR: { parallel_mxn: -400, points: [{ label: '1Y', days: 365, dv01_mxn: -500 }] },
  },
  errors: [],
};

const TRADES: Trade[] = [
  {
    id: 1,
    product: 'irs',
    counterparty: 'Banco A',
    params: {},
    notional: 1e6,
    currency: 'MXN',
    maturity: '2027-11-10',
    created_at: '2026-11-10',
  },
  {
    id: 2,
    product: 'fx_forward',
    counterparty: 'Banco B',
    params: {},
    notional: 1e5,
    currency: 'MXN',
    maturity: '2027-05-10',
    created_at: '2026-11-10',
  },
];

function scenariosFor(snapshot: string): ScenariosResponse {
  return {
    snapshot,
    scenarios: [
      'TIIE-F +50 pb',
      'TIIE-F -50 pb',
      'SOFR +50 pb',
      'SOFR -50 pb',
      'TIIE-F steepener 25 pb',
      'SOFR steepener 25 pb',
      'USDMXN +10 %',
      'USDMXN -10 %',
    ].map((name, i) => ({
      name,
      total_mxn: 100 * (i + 1) + 5,
      trades: [
        { id: 1, pnl_mxn: 100 * (i + 1), error: null },
        { id: 2, pnl_mxn: i === 3 ? null : 5, error: i === 3 ? 'Sin cotización' : null },
      ],
    })),
  };
}

const VAR: VarResponse = {
  snapshot: 'MX-DEMO',
  var_mxn: 1234567.891,
  horizon_days: 10,
  confidence: 0.99,
  factors: [
    { factor: 'TIIE-F', unit: 'bp', exposure_mxn: 1000, daily_vol: 4, var_mxn: 700 },
    { factor: 'SOFR', unit: 'bp', exposure_mxn: 400, daily_vol: 5, var_mxn: 300 },
    { factor: 'USDMXN', unit: 'ret', exposure_mxn: 200000, daily_vol: 0.0075, var_mxn: 900 },
  ],
  errors: [],
};

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderScreen() {
  return render(
    <SnapshotProvider>
      <SwitchTo id="OTRO" />
      <RiskScreen />
    </SnapshotProvider>,
  );
}

const varCard = () => screen.getByRole('region', { name: 'Valor en riesgo (VaR)' });

beforeEach(() => {
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.riskDv01.mockImplementation(async (id: string) => ({ ...DV01, snapshot: id }));
  mocks.riskScenarios.mockImplementation(async (id: string) => scenariosFor(id));
  mocks.riskVar.mockImplementation(async (id: string) => ({ ...VAR, snapshot: id }));
  mocks.listTrades.mockResolvedValue(TRADES);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('RiskScreen: tarjeta VaR', () => {
  it('muestra el VaR total y los tres factores', async () => {
    renderScreen();
    const card = varCard();

    expect(await within(card).findByText('MXN 1,234,567.89')).toBeTruthy();
    expect(mocks.riskVar).toHaveBeenCalledWith('MX-DEMO', 10, 0.99);
    for (const f of ['TIIE-F', 'SOFR', 'USDMXN']) {
      expect(within(card).getByRole('cell', { name: f })).toBeTruthy();
    }
    expect(within(card).getByText('0.7500 %')).toBeTruthy();
    expect(within(card).getByText('4.00 pb')).toBeTruthy();
  });

  it('cambiar el horizonte vuelve a llamar a riskVar con el valor nuevo', async () => {
    renderScreen();
    await within(varCard()).findByText('MXN 1,234,567.89');

    fireEvent.change(screen.getByLabelText('Horizonte (días)'), { target: { value: '5' } });

    await waitFor(() => expect(mocks.riskVar).toHaveBeenLastCalledWith('MX-DEMO', 5, 0.99));
  });

  it('el encabezado dice "1 día" en singular y "días" en cualquier otro horizonte', async () => {
    renderScreen();
    expect(await within(varCard()).findByText('VaR 99 % a 10 días')).toBeTruthy();
    mocks.riskVar.mockResolvedValueOnce({ ...VAR, horizon_days: 1 });

    fireEvent.change(screen.getByLabelText('Horizonte (días)'), { target: { value: '1' } });

    expect(await within(varCard()).findByText('VaR 99 % a 1 día')).toBeTruthy();
  });

  it('la confianza se captura en % y se envía en decimal', async () => {
    renderScreen();
    await within(varCard()).findByText('MXN 1,234,567.89');

    fireEvent.change(screen.getByLabelText('Confianza (%)'), { target: { value: '95' } });

    await waitFor(() => expect(mocks.riskVar).toHaveBeenLastCalledWith('MX-DEMO', 10, 0.95));
  });

  it('el error del backend aparece junto al input que lo causa', async () => {
    renderScreen();
    await within(varCard()).findByText('MXN 1,234,567.89');
    mocks.riskVar.mockRejectedValueOnce(new ApiError(400, 'El horizonte debe ser mayor que 0', 'horizon_days'));

    fireEvent.change(screen.getByLabelText('Horizonte (días)'), { target: { value: '0' } });

    const msg = await within(varCard()).findByText('El horizonte debe ser mayor que 0');
    expect(msg.parentElement?.contains(screen.getByLabelText('Horizonte (días)'))).toBe(true);
    expect(screen.getByLabelText('Horizonte (días)').getAttribute('aria-invalid')).toBe('true');
    expect(within(varCard()).queryByText('MXN 1,234,567.89')).toBeNull();
  });

  it('un campo vacío no llama al backend y marca el input', async () => {
    renderScreen();
    await within(varCard()).findByText('MXN 1,234,567.89');
    mocks.riskVar.mockClear();

    fireEvent.change(screen.getByLabelText('Confianza (%)'), { target: { value: '' } });

    await within(varCard()).findByText('Ingresa un número válido');
    expect(mocks.riskVar).not.toHaveBeenCalled();
  });
});

describe('RiskScreen: escalera DV01', () => {
  it('muestra los totales y dibuja una serie por curva', async () => {
    renderScreen();
    const card = screen.getByRole('region', { name: 'Escalera DV01' });

    expect(await within(card).findByText('MXN -1,500.00')).toBeTruthy();
    expect(within(card).getByText('MXN -1,400.00')).toBeTruthy();
    expect(within(card).getByText('TIIE-F paralelo')).toBeTruthy();
    expect(within(card).getByText('SOFR paralelo')).toBeTruthy();

    await waitFor(() => {
      const option = mocks.chart.setOption.mock.calls.map((c) => c[0]).find((o) => o.series?.length);
      expect(option.series.map((s: { name: string }) => s.name)).toEqual(['TIIE-F', 'SOFR']);
      // Pilares ordenados por días: 364 (TIIE-F), 365 (SOFR), 728 (TIIE-F).
      expect(option.xAxis.data).toEqual(['13x28', '1Y', '26x28']);
      expect(option.series[0].data).toEqual([-400, null, -600]);
      expect(option.series[1].data).toEqual([null, -500, null]);
    });
  });
});

describe('RiskScreen: escenarios', () => {
  it('pide el set fijo de ocho escenarios', async () => {
    renderScreen();
    await waitFor(() => expect(mocks.riskScenarios).toHaveBeenCalled());

    const [snapshot, specs] = mocks.riskScenarios.mock.calls[0];
    expect(snapshot).toBe('MX-DEMO');
    expect(specs).toEqual([
      { name: 'TIIE-F +50 pb', type: 'parallel', curve: 'TIIE-F', bp: 50 },
      { name: 'TIIE-F -50 pb', type: 'parallel', curve: 'TIIE-F', bp: -50 },
      { name: 'SOFR +50 pb', type: 'parallel', curve: 'SOFR', bp: 50 },
      { name: 'SOFR -50 pb', type: 'parallel', curve: 'SOFR', bp: -50 },
      { name: 'TIIE-F steepener 25 pb', type: 'steepener', curve: 'TIIE-F', bp: 25 },
      { name: 'SOFR steepener 25 pb', type: 'steepener', curve: 'SOFR', bp: 25 },
      { name: 'USDMXN +10 %', type: 'fx_spot', pct: 10 },
      { name: 'USDMXN -10 %', type: 'fx_spot', pct: -10 },
    ]);
  });

  it('arma una columna por escenario, una fila por operación y la fila de total', async () => {
    renderScreen();
    await waitFor(() => {
      const rowData = mocks.grid.setGridOption.mock.calls.filter((c) => c[0] === 'rowData').pop();
      expect(rowData?.[1]).toHaveLength(2);
    });

    const options = mocks.createGrid.mock.calls[0][1];
    expect(options.columnDefs.map((c: { headerName: string }) => c.headerName)).toEqual([
      'Operación',
      'TIIE-F +50 pb',
      'TIIE-F -50 pb',
      'SOFR +50 pb',
      'SOFR -50 pb',
      'TIIE-F steepener 25 pb',
      'SOFR steepener 25 pb',
      'USDMXN +10 %',
      'USDMXN -10 %',
    ]);

    const calls = mocks.grid.setGridOption.mock.calls;
    const rows = calls.filter((c) => c[0] === 'rowData').pop()?.[1];
    const total = calls.filter((c) => c[0] === 'pinnedBottomRowData').pop()?.[1];
    expect(rows[0]).toMatchObject({ label: '#1 irs · Banco A', s0: 100, s7: 800 });
    expect(rows[1]).toMatchObject({ label: '#2 fx_forward · Banco B', s0: 5, s3: null, e3: 'Sin cotización' });
    expect(total).toEqual([expect.objectContaining({ label: 'Total', s0: 105, s7: 805 })]);
  });

  it('formatea n/d cuando una operación no se pudo valuar', async () => {
    renderScreen();
    await waitFor(() => expect(mocks.createGrid).toHaveBeenCalled());
    const col = mocks.createGrid.mock.calls[0][1].columnDefs[4];
    expect(col.valueFormatter({ value: null })).toBe('n/d');
    expect(col.valueFormatter({ value: 1234.5 })).toBe('1,235'); // sin decimales: 8 escenarios caben en 1280 px
    expect(col.tooltipValueGetter({ data: { e3: 'Sin cotización' } })).toBe('Sin cotización');
    expect(await screen.findByText(/Algunas celdas no se pudieron valuar/)).toBeTruthy();
  });
});

describe('RiskScreen: cambio de snapshot', () => {
  it('recarga DV01, escenarios y VaR con el snapshot nuevo', async () => {
    renderScreen();
    await within(varCard()).findByText('MXN 1,234,567.89');

    fireEvent.click(screen.getByRole('button', { name: 'cambiar a OTRO' }));

    await waitFor(() => {
      expect(mocks.riskDv01).toHaveBeenLastCalledWith('OTRO');
      expect(mocks.riskScenarios).toHaveBeenLastCalledWith('OTRO', expect.any(Array));
      expect(mocks.riskVar).toHaveBeenLastCalledWith('OTRO', 10, 0.99);
    });
  });
});
