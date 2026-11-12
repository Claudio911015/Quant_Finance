import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { Snapshot } from '../api/types';
import { SnapshotProvider } from '../state/SnapshotContext';
import {
  CREDIT_CURVES_FIXTURE,
  INCREMENTAL_FIXTURE,
  XVA_FIXTURE,
  XVA_PARAMS_FIXTURE,
  XVA_SENSITIVITIES_FIXTURE,
} from './xva/fixtures';
import XvaScreen from './XvaScreen';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  createTrade: vi.fn(),
  getXva: vi.fn(),
  getXvaParams: vi.fn(),
  getXvaSensitivities: vi.fn(),
  putXvaParams: vi.fn(),
  xvaIncremental: vi.fn(),
  getCreditCurves: vi.fn(),
  putCreditCurve: vi.fn(),
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, listSnapshots: mocks.listSnapshots, getSnapshot: mocks.getSnapshot, createTrade: mocks.createTrade };
});

vi.mock('../api/xvaClient', () => ({
  getXva: mocks.getXva,
  getXvaParams: mocks.getXvaParams,
  getXvaSensitivities: mocks.getXvaSensitivities,
  putXvaParams: mocks.putXvaParams,
  xvaIncremental: mocks.xvaIncremental,
  getCreditCurves: mocks.getCreditCurves,
  putCreditCurve: mocks.putCreditCurve,
}));

// echarts pinta en canvas, que jsdom no tiene; aquí solo importa qué opción recibe cada gráfica.
const charts: { option: { series?: { name?: string; data: unknown[] }[] }; ariaLabel?: string }[] = [];
vi.mock('../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: (typeof charts)[number]) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

const [ALFA, BETA] = XVA_FIXTURE.counterparties;
const lastChart = (label: string) => [...charts].reverse().find((c) => c.ariaLabel === label);

function renderScreen() {
  return render(
    <SnapshotProvider>
      <XvaScreen />
    </SnapshotProvider>,
  );
}

beforeEach(() => {
  charts.length = 0;
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.getXva.mockImplementation(async (id: string) => ({ ...XVA_FIXTURE, snapshot: id }));
  mocks.getXvaParams.mockResolvedValue(XVA_PARAMS_FIXTURE);
  mocks.putXvaParams.mockImplementation(async (body) => ({ ...XVA_PARAMS_FIXTURE, ...body }));
  mocks.xvaIncremental.mockResolvedValue(INCREMENTAL_FIXTURE);
  mocks.getXvaSensitivities.mockResolvedValue(XVA_SENSITIVITIES_FIXTURE);
  mocks.getCreditCurves.mockResolvedValue(CREDIT_CURVES_FIXTURE);
  mocks.putCreditCurve.mockResolvedValue(CREDIT_CURVES_FIXTURE.curves[0]);
  mocks.createTrade.mockResolvedValue({ id: 12 });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('XvaScreen: tabla y avisos', () => {
  it('muestra el aviso permanente de XVA informativo y la nota de colateral aun antes de tener datos', () => {
    mocks.getXva.mockReturnValue(new Promise(() => {}));
    renderScreen();
    expect(screen.getByRole('note').textContent).toContain(
      'XVA informativo: no entra al PV ni a la contabilidad',
    );
    expect(screen.getByText(/Exposición sin colateral ni margen/)).toBeTruthy();
    expect(screen.getByText('Calculando XVA…')).toBeTruthy();
  });

  it('pide el XVA del snapshot activo y lista las tres contrapartes', async () => {
    renderScreen();
    const table = await screen.findByRole('table', { name: 'XVA por contraparte' });
    expect(mocks.getXva).toHaveBeenCalledWith('MX-DEMO');
    expect(within(table).getAllByRole('row')).toHaveLength(1 + 3);
    expect(screen.getByRole('heading', { level: 1, name: 'XVA' })).toBeTruthy();
  });

  it('la operación excluida se explica y nunca aparece el id del producto', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    expect(screen.getByText(/El XVA solo cubre swaps de tasa y cross currency swaps: Forward FX se excluye/)).toBeTruthy();
    for (const raw of ['irs', 'xccy_swap', 'fx_forward']) expect(screen.queryByText(raw)).toBeNull();
    expect(screen.getAllByText(/Swap de tasas \(IRS\)/).length).toBeGreaterThan(0);
  });

  it('elegir otra contraparte cambia la gráfica de perfil y la lista de operaciones', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    expect(lastChart('Perfil de exposición')!.option.series![0].data).toEqual(ALFA.profile.map((p) => p.epe_mxn));
    expect(screen.getByRole('heading', { name: `Perfil de ${ALFA.counterparty}` })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: BETA.counterparty }));
    expect(lastChart('Perfil de exposición')!.option.series![0].data).toEqual(BETA.profile.map((p) => p.epe_mxn));
    expect(screen.getByRole('heading', { name: `Perfil de ${BETA.counterparty}` })).toBeTruthy();
    const trades = screen.getByRole('region', { name: `Operaciones de ${BETA.counterparty}` });
    expect(within(trades).getByText(/Cross currency swap/)).toBeTruthy();
  });

  it('las sensibilidades van bajo el perfil, son de la contraparte elegida y se piden a petición', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    expect(mocks.getXvaSensitivities).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: BETA.counterparty }));
    expect(screen.getByRole('heading', { name: `Sensibilidades de ${BETA.counterparty}` })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Calcular sensibilidades' }));
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
    expect(mocks.getXvaSensitivities).toHaveBeenCalledWith('MX-DEMO', BETA.counterparty);
  });

  it('declara los supuestos y el modelo del snapshot', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    const card = screen.getByRole('region', { name: 'Supuestos y modelo' });
    expect(within(card).getByText(XVA_FIXTURE.assumptions[0])).toBeTruthy();
    expect(within(card).getByText('Volatilidad USDMXN')).toBeTruthy();
    expect(within(card).getByText(/ATM a 1 año de la superficie/)).toBeTruthy();
    expect(within(card).getByText('11.90 %')).toBeTruthy();
    expect(within(card).getByText(/propia/i)).toBeTruthy();
  });

  it('rotula la volatilidad USDMXN por omisión en vez de dejar el campo vacío', async () => {
    mocks.getXva.mockImplementation(async (id: string) => ({
      ...XVA_FIXTURE,
      snapshot: id,
      model: { ...XVA_FIXTURE.model, fx_vol_source: 'default' as const },
    }));
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    const card = screen.getByRole('region', { name: 'Supuestos y modelo' });
    expect(within(card).getByText(/valor por omisión/)).toBeTruthy();
    expect(within(card).queryByText(/ATM a 1 año de la superficie/)).toBeNull();
  });

  it('si el XVA falla muestra el error y deja a la vista el aviso', async () => {
    mocks.getXva.mockRejectedValue(new ApiError(500, 'No se pudo calcular el XVA'));
    renderScreen();
    expect((await screen.findByText('No se pudo calcular el XVA')).getAttribute('role')).toBe('alert');
    expect(screen.getByText(/XVA informativo/)).toBeTruthy();
  });
});

describe('XvaScreen: edición y recarga', () => {
  it('guardar los parámetros recalcula el XVA', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    const spread = (await screen.findByLabelText('Spread de fondeo (pb)')) as HTMLInputElement;
    fireEvent.change(spread, { target: { value: '80' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));
    await waitFor(() => expect(mocks.getXva).toHaveBeenCalledTimes(2));
    expect(mocks.putXvaParams).toHaveBeenCalledWith(expect.objectContaining({ funding_spread: 0.008 }));
  });

  it('guardar los parámetros descarta las sensibilidades calculadas, que ya no son las del XVA', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular sensibilidades' }));
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
    fireEvent.click(await screen.findByRole('button', { name: 'Guardar parámetros' }));
    await waitFor(() => expect(mocks.getXva).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('table', { name: 'Sensibilidad por curva y pilar' })).toBeNull();
  });

  it('guardar una curva de crédito recalcula el XVA', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    await screen.findByLabelText('Entidad');
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));
    await waitFor(() => expect(mocks.getXva).toHaveBeenCalledTimes(2));
    expect(mocks.putCreditCurve).toHaveBeenCalledWith('propia', expect.objectContaining({ snapshot: 'MX-DEMO' }));
  });

  it('pactar la operación calculada recarga el XVA', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));
    await screen.findByRole('table', { name: 'XVA antes y después' });
    fireEvent.click(screen.getByRole('button', { name: 'Pactar' }));
    await waitFor(() => expect(mocks.createTrade).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.getXva).toHaveBeenCalledTimes(2));
    expect(mocks.createTrade).toHaveBeenCalledWith(
      expect.objectContaining({ snapshot: 'MX-DEMO', counterparty: ALFA.counterparty, product: 'irs' }),
    );
  });

  it('las curvas de crédito se rotulan como sintéticas', async () => {
    renderScreen();
    await screen.findByRole('table', { name: 'XVA por contraparte' });
    const region = await screen.findByRole('region', { name: 'Curvas de crédito' });
    expect(within(region).getByText('Sintética')).toBeTruthy();
  });
});
