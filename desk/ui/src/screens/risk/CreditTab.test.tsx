import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { CreditCounterparty, CreditExposureResponse, CreditParams } from '../../api/riskTypes';
import type { Snapshot } from '../../api/types';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { CreditTab, profileOption } from './CreditTab';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  creditExposure: vi.fn(),
  listCreditParams: vi.fn(),
  setCreditParams: vi.fn(),
}));

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, listSnapshots: mocks.listSnapshots, getSnapshot: mocks.getSnapshot };
});

vi.mock('../../api/riskClient', () => ({
  creditExposure: mocks.creditExposure,
  listCreditParams: mocks.listCreditParams,
  setCreditParams: mocks.setCreditParams,
}));

// echarts pinta en canvas, que jsdom no tiene; aquí solo importa qué opción recibe la gráfica.
const charts: { option: { series?: { name?: string; data: unknown[] }[] }; ariaLabel?: string }[] = [];
vi.mock('../../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: (typeof charts)[number]) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

const ALFA: CreditCounterparty = {
  counterparty: 'Banco Alfa (sintético)',
  hazard_rate: 0.01,
  recovery: 0.4,
  assumed: true,
  assumed_note: 'Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)',
  pv_mxn: -1250000,
  cva_mxn: 3456.7,
  netting_sets: [{ curve: 'TIIE-F', currency: 'MXN', trades: [1, 7], pv_mxn: -1250000, cva_mxn: 3456.7 }],
  profile: [
    { date: '2026-11-10', t: 0, ee_mxn: 0, pfe_mxn: 0 },
    { date: '2026-12-10', t: 0.0822, ee_mxn: 812000, pfe_mxn: 3100000 },
    { date: '2027-01-10', t: 0.1644, ee_mxn: 900000, pfe_mxn: 3500000 },
  ],
  excluded: [
    {
      id: 4,
      product: 'fx_forward',
      reason: 'La exposición simulada solo cubre swaps de tasa (irs): fx_forward se excluye',
    },
  ],
};

const BETA: CreditCounterparty = {
  counterparty: 'Banco Beta (sintético)',
  hazard_rate: 0.02,
  recovery: 0.35,
  assumed: false,
  assumed_note: null,
  pv_mxn: 540000,
  cva_mxn: 8000,
  netting_sets: [{ curve: 'TIIE-F', currency: 'MXN', trades: [2], pv_mxn: 540000, cva_mxn: 8000 }],
  profile: [
    { date: '2026-11-10', t: 0, ee_mxn: 540000, pfe_mxn: 540000 },
    { date: '2026-12-10', t: 0.0822, ee_mxn: 600000, pfe_mxn: 1200000 },
  ],
  excluded: [],
};

const EXPOSURE: CreditExposureResponse = {
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  n_paths: 500,
  seed: 42,
  pfe_quantile: 0.95,
  notice: 'CVA informativo: no entra al PV ni a la contabilidad de coberturas',
  counterparties: [ALFA, BETA],
  excluded: [{ ...ALFA.excluded[0], counterparty: ALFA.counterparty }],
  warnings: [],
};

const PARAMS: CreditParams[] = [
  { counterparty: ALFA.counterparty, hazard_rate: 0.01, recovery: 0.4, as_of: null, assumed: true, history: [] },
  {
    counterparty: BETA.counterparty,
    hazard_rate: 0.02,
    recovery: 0.35,
    as_of: '2026-11-05',
    assumed: false,
    history: [
      { hazard_rate: 0.02, recovery: 0.35, as_of: '2026-11-05', created_at: '2026-11-05T10:00:00+00:00' },
      { hazard_rate: 0.015, recovery: 0.4, as_of: '2026-10-01', created_at: '2026-10-01T10:00:00+00:00' },
    ],
  },
];

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderTab() {
  return render(
    <SnapshotProvider>
      <SwitchTo id="OTRO" />
      <CreditTab />
    </SnapshotProvider>,
  );
}

const lastChart = () => charts[charts.length - 1];
const pickButton = (name: string) => screen.getByRole('button', { name });

beforeEach(() => {
  charts.length = 0;
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.creditExposure.mockImplementation(async (id: string) => ({ ...EXPOSURE, snapshot: id }));
  mocks.listCreditParams.mockResolvedValue(PARAMS);
  mocks.setCreditParams.mockImplementation(async (body: { counterparty: string }) => ({
    ...PARAMS[0],
    counterparty: body.counterparty,
  }));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('CreditTab: contrapartes y CVA', () => {
  it('indica que simula mientras llega la exposición', async () => {
    mocks.creditExposure.mockReturnValue(new Promise(() => {}));
    renderTab();
    expect(await screen.findByText('Simulando exposición…')).toBeTruthy();
  });

  it('muestra la banda de CVA informativo y la tabla de contrapartes con su CVA', async () => {
    renderTab();
    const note = await screen.findByRole('note');
    expect(note.textContent).toBe('CVA informativo: no entra al PV ni a la contabilidad de coberturas');

    const table = screen.getByRole('table', { name: '' });
    const alfa = within(table).getByRole('button', { name: ALFA.counterparty }).closest('tr') as HTMLElement;
    expect(within(alfa).getByText('MXN -1,250,000.00')).toBeTruthy();
    expect(within(alfa).getByText('MXN 3,456.70')).toBeTruthy();
    expect(within(alfa).getByText('1.0000 %')).toBeTruthy();
    expect(within(alfa).getByText('40.0000 %')).toBeTruthy();
    expect(mocks.creditExposure).toHaveBeenCalledWith('MX-DEMO');

    const beta = within(table).getByRole('button', { name: BETA.counterparty }).closest('tr') as HTMLElement;
    expect(within(beta).getByText('MXN 8,000.00')).toBeTruthy();
    expect(within(beta).getByText('2.0000 %')).toBeTruthy();
    expect(within(beta).getByText('35.0000 %')).toBeTruthy();
  });

  it('marca como "Supuesto" solo los parámetros por omisión, con su nota como título', async () => {
    renderTab();
    await screen.findByRole('note');
    const marks = screen.getAllByText('Supuesto');
    expect(marks).toHaveLength(1);
    expect(marks[0].getAttribute('title')).toBe(ALFA.assumed_note);
    expect(marks[0].closest('tr')?.textContent).toContain(ALFA.counterparty);
  });

  it('pone el pie con las trayectorias y el alcance', async () => {
    renderTab();
    await screen.findByRole('note');
    expect(
      screen.getByText(
        '500 trayectorias Hull-White, semilla fija; solo swaps de tasa; sin colateral ni compensación entre monedas.',
      ),
    ).toBeTruthy();
  });

  it('un error del backend va en un aviso de error', async () => {
    mocks.creditExposure.mockRejectedValue(new ApiError(404, 'Snapshot no encontrado', 'snapshot'));
    renderTab();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Snapshot no encontrado');
  });
});

describe('CreditTab: perfil de la contraparte elegida', () => {
  it('abre con la primera contraparte y muestra sus conjuntos de compensación y excluidas', async () => {
    renderTab();
    await screen.findByRole('note');

    expect(screen.getByRole('img', { name: 'Perfil de exposición' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: `Perfil de ${ALFA.counterparty}` })).toBeTruthy();
    expect(pickButton(ALFA.counterparty).getAttribute('aria-pressed')).toBe('true');
    expect(pickButton(BETA.counterparty).getAttribute('aria-pressed')).toBe('false');

    const sets = screen.getByRole('region', { name: 'Conjuntos de compensación' });
    expect(within(sets).getByText('TIIE-F (MXN)')).toBeTruthy();
    expect(sets.textContent).toContain('#1, #7');

    // Lo que la exposición no cubre se lista con el motivo del backend, en un aviso.
    const reason = screen.getByText(`Operación #4: ${ALFA.excluded[0].reason}`);
    expect(reason.closest('.radv-note--warn')).not.toBeNull();
  });

  it('cambiar de contraparte cambia la gráfica, los conjuntos y las excluidas', async () => {
    renderTab();
    await screen.findByRole('note');
    expect(lastChart().option.series?.[0].data).toEqual([0, 812000, 900000]);

    fireEvent.click(pickButton(BETA.counterparty));

    await waitFor(() => expect(lastChart().option.series?.[0].data).toEqual([540000, 600000]));
    expect(pickButton(BETA.counterparty).getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByText(/Operación #4/)).toBeNull();
    const sets = screen.getByRole('region', { name: 'Conjuntos de compensación' });
    expect(sets.textContent).toContain('#2');
  });

  it('profileOption: dos líneas, EE y PFE, contra la fecha', () => {
    const option = profileOption(ALFA, 0.95) as {
      xAxis: { data: string[] };
      series: { name: string; type: string; data: number[] }[];
    };
    expect(option.xAxis.data).toEqual(['2026-11-10', '2026-12-10', '2027-01-10']);
    expect(option.series.map((s) => [s.name, s.type])).toEqual([
      ['EE', 'line'],
      ['PFE 95 %', 'line'],
    ]);
    expect(option.series[0].data).toEqual([0, 812000, 900000]);
    expect(option.series[1].data).toEqual([0, 3100000, 3500000]);
    // Sin cuantil, la leyenda queda en "PFE".
    expect((profileOption(ALFA) as { series: { name: string }[] }).series[1].name).toBe('PFE');
  });

  it('una contraparte sin swaps vivos dice que no hay perfil y no dibuja la gráfica', async () => {
    const vacia: CreditCounterparty = {
      ...BETA,
      pv_mxn: 0,
      cva_mxn: 0,
      netting_sets: [],
      profile: [],
      excluded: [{ id: 9, product: 'cap_floor', reason: 'cap_floor se excluye' }],
    };
    mocks.creditExposure.mockResolvedValue({ ...EXPOSURE, counterparties: [vacia] });
    renderTab();
    await screen.findByRole('note');

    expect(screen.getByText(/no hay perfil de exposición/)).toBeTruthy();
    expect(screen.queryByRole('img', { name: 'Perfil de exposición' })).toBeNull();
    expect(screen.getByText('Operación #9: cap_floor se excluye')).toBeTruthy();
  });

  it('sin contrapartes con operaciones vivas lo dice', async () => {
    mocks.creditExposure.mockResolvedValue({ ...EXPOSURE, counterparties: [], excluded: [] });
    renderTab();
    expect(await screen.findByText(/No hay contrapartes con operaciones vivas/)).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Parámetros de crédito' })).toBeNull();
  });
});

describe('CreditTab: parámetros', () => {
  const hazardInput = () => screen.getByLabelText('Prob. de incumplimiento anual (%)') as HTMLInputElement;
  const recoveryInput = () => screen.getByLabelText('Recuperación (%)') as HTMLInputElement;

  it('el formulario parte de los parámetros vigentes de la contraparte elegida', async () => {
    renderTab();
    await screen.findByRole('note');
    expect(hazardInput().value).toBe('1');
    expect(recoveryInput().value).toBe('40');

    fireEvent.click(pickButton(BETA.counterparty));
    await waitFor(() => expect(hazardInput().value).toBe('2'));
    expect(recoveryInput().value).toBe('35');
  });

  it('enviar convierte % a decimal, guarda y recarga la exposición', async () => {
    renderTab();
    await screen.findByRole('note');
    expect(mocks.creditExposure).toHaveBeenCalledTimes(1);

    fireEvent.change(hazardInput(), { target: { value: '2.5' } });
    fireEvent.change(recoveryInput(), { target: { value: '35' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));

    await waitFor(() => expect(mocks.creditExposure).toHaveBeenCalledTimes(2));
    expect(mocks.setCreditParams).toHaveBeenCalledWith({
      counterparty: ALFA.counterparty,
      hazard_rate: 0.025,
      recovery: 0.35,
    });
    expect(mocks.creditExposure).toHaveBeenLastCalledWith('MX-DEMO');
  });

  it('un 400 de recuperación va bajo su campo y no recarga', async () => {
    mocks.setCreditParams.mockRejectedValue(new ApiError(400, 'recovery debe ser menor que 1', 'recovery'));
    renderTab();
    await screen.findByRole('note');

    fireEvent.change(recoveryInput(), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));

    const message = await screen.findByText('recovery debe ser menor que 1');
    expect(message.id).toBe('credittab-recovery-error');
    expect(recoveryInput().getAttribute('aria-describedby')).toBe('credittab-recovery-error');
    expect(hazardInput().getAttribute('aria-invalid')).toBeNull();
    expect(mocks.creditExposure).toHaveBeenCalledTimes(1);
  });

  it('un error que no es de un campo va en un aviso de error', async () => {
    mocks.setCreditParams.mockRejectedValue(new ApiError(404, 'Contraparte no encontrada', 'counterparty'));
    renderTab();
    await screen.findByRole('note');

    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Contraparte no encontrada');
  });

  it('un valor no numérico no llama a la API', async () => {
    renderTab();
    await screen.findByRole('note');

    fireEvent.change(hazardInput(), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));

    expect(await screen.findByText('Ingresa un número válido')).toBeTruthy();
    expect(mocks.setCreditParams).not.toHaveBeenCalled();
  });

  it('lista el historial de parámetros de la contraparte, o dice que no hay', async () => {
    renderTab();
    await screen.findByRole('note');
    // Alfa no tiene filas guardadas.
    expect(await screen.findByText('Sin parámetros capturados para esta contraparte.')).toBeTruthy();

    fireEvent.click(pickButton(BETA.counterparty));
    const history = await screen.findByText('2026-10-01');
    const row = history.closest('tr') as HTMLElement;
    expect(within(row).getByText('1.5000 %')).toBeTruthy();
    expect(within(row).getByText('40.0000 %')).toBeTruthy();
    expect(screen.getByText('2026-11-05')).toBeTruthy();
  });
});

describe('CreditTab: cambio de snapshot', () => {
  it('vuelve a simular con el snapshot nuevo', async () => {
    renderTab();
    await screen.findByRole('note');

    fireEvent.click(screen.getByRole('button', { name: 'cambiar a OTRO' }));

    await waitFor(() => expect(mocks.creditExposure).toHaveBeenLastCalledWith('OTRO'));
    await waitFor(() => expect(screen.getByRole('note')).toBeTruthy());
  });
});
