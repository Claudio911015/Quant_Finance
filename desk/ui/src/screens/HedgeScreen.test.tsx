import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  EffectivenessResponse,
  HedgeDetail,
  HedgePeriod,
  Snapshot,
  SnapshotSummary,
} from '../api/types';
import { ApiError } from '../api/client';
import { SnapshotProvider, useSnapshot } from '../state/SnapshotContext';
import HedgeScreen from './HedgeScreen';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  getHedge: vi.fn(),
  hedgeEffectiveness: vi.fn(),
  closeHedgePeriod: vi.fn(),
  dedesignateHedge: vi.fn(),
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    getHedge: mocks.getHedge,
    hedgeEffectiveness: mocks.hedgeEffectiveness,
    closeHedgePeriod: mocks.closeHedgePeriod,
    dedesignateHedge: mocks.dedesignateHedge,
  };
});

const SNAPSHOTS = [
  { id: 'MX-DEMO', label: 'Demo MX', as_of: '2026-11-10' },
  { id: 'D1', label: 'Rodado', as_of: '2026-12-15' },
] as unknown as SnapshotSummary[];

const NOTICE =
  'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9';

function period(over: Partial<HedgePeriod> = {}): HedgePeriod {
  return {
    id: 1,
    snapshot: 'D1',
    as_of: '2026-12-15',
    created_at: '2026-12-15T10:00:00+00:00',
    prev_snapshot: 'MX-DEMO',
    prev_as_of: '2026-11-10',
    data_quality: 'synthetic',
    trade_status: 'viva',
    hedge_type: 'cash_flow',
    fraction: 1,
    pv_inst: -125000,
    pv_hypo: -125000,
    inst_cum: -125000,
    hypo_cum: -125000,
    d_inst_cum: -125000,
    d_hypo_cum: -125000,
    settled_period: 31000,
    settled_flows: [],
    oci: -125000,
    d_oci: -125000,
    ineffectiveness: 0,
    recycled: 31000,
    item_adjustment: 0,
    fv_result: 0,
    instrument_pnl: -94000,
    identity_residual: 0,
    entries: [
      { account: 'Derivado (valor razonable)', debit: 0, credit: 125000, memo: 'Cambio de valor razonable del derivado (fracción designada)' },
      { account: 'ORI — reserva de cobertura', debit: 125000, credit: 0, memo: 'Porción efectiva a la reserva de cobertura' },
      { account: 'Efectivo', debit: 31000, credit: 0, memo: 'Liquidación del derivado en el periodo' },
      { account: 'Resultados — partida cubierta (reciclaje)', debit: 0, credit: 31000, memo: 'Reciclaje: flujo cubierto ocurrido en el periodo' },
    ],
    warnings: [],
    ...over,
  };
}

const HEDGE: HedgeDetail = {
  id: 1,
  trade_id: 8,
  product: 'irs',
  counterparty: 'Banco Alfa (sintético)',
  fraction: 0.5,
  hedge_type: 'cash_flow',
  item_kind: 'floating_loan',
  item_terms: {
    index: 'TIIE-F',
    notional: 500000000,
    start_date: '2026-11-10',
    maturity_date: '2027-11-09',
    side: 'pays_floating',
  },
  hedge_ratio: 1,
  designation_date: '2026-11-10',
  designation_snapshot: 'MX-DEMO',
  documentation: {
    risk_management_objective: 'Fijar el costo del crédito sindicado',
    hedged_risk: 'Variabilidad de los intereses por TIIE de Fondeo',
    effectiveness_method: 'Términos críticos y escenarios con derivado hipotético',
    ineffectiveness_sources: 'Diferencias de fechas y nocional',
  },
  hypothetical: {
    product: 'irs',
    trade_date: '2026-11-10',
    start_date: '2026-11-10',
    maturity_date: '2027-11-09',
    params: {},
  },
  designation: { snapshot: 'MX-DEMO', as_of: '2026-11-10', data_quality: 'synthetic', pv_inst: 0, pv_hypo: 0 },
  status: 'activa',
  dedesignation: null,
  oci_balance: -125000,
  last_close: '2026-12-15',
  events: [],
  periods: [period()],
  created_at: '2026-11-10T10:00:00+00:00',
};

const EFF: EffectivenessResponse = {
  id: 1,
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  critical_terms: [
    { term: 'notional', label: 'Nocional', instrument: 250000000, item: 250000000, result: 'match' },
    { term: 'index', label: 'Índice', instrument: 'TIIE-F', item: 'TIIE-F', result: 'match' },
    { term: 'maturity_date', label: 'Vencimiento', instrument: '2027-11-09', item: '2027-12-07', result: 'mismatch' },
  ],
  scenarios: [
    { name: 'TIIE-F +50 pb', d_inst: 2400000, d_hypo: 2400000, ratio: 1 },
    { name: 'SOFR +50 pb', d_inst: 0, d_hypo: 0, ratio: null },
  ],
  economic_relationship: true,
  in_reference_range: 1,
  scenarios_counted: 1,
  reference_note: 'IFRS 9 no fija un umbral de efectividad: el rango 80 %–125 % se informa solo como referencia',
  warnings: [],
};

const FAIR_VALUE_HEDGE: HedgeDetail = {
  ...HEDGE,
  hedge_type: 'fair_value',
  item_kind: 'fixed_loan',
  item_terms: {
    index: 'TIIE-F',
    notional: 300000000,
    start_date: '2026-11-10',
    maturity_date: '2028-11-03',
    side: 'pays_fixed',
  },
  oci_balance: 0,
  periods: [
    period({ hedge_type: 'fair_value', oci: 0, d_oci: 0, recycled: 0, item_adjustment: 80000, fv_result: 5000, ineffectiveness: 1500 }),
  ],
};

const DEDESIGNATED: HedgeDetail = {
  ...HEDGE,
  status: 'desdesignada',
  dedesignation: { date: '2027-01-10', reason: 'Prepago del crédito', frozen_oci: -125000 },
};

function setup(hedge: HedgeDetail = HEDGE) {
  mocks.listSnapshots.mockResolvedValue(SNAPSHOTS);
  mocks.getSnapshot.mockImplementation(async (id: string) => {
    const s = SNAPSHOTS.find((x) => x.id === id)!;
    return { id: s.id, as_of: s.as_of } as unknown as Snapshot;
  });
  mocks.getHedge.mockResolvedValue(hedge);
  mocks.hedgeEffectiveness.mockResolvedValue(EFF);
  mocks.closeHedgePeriod.mockResolvedValue(period());
  mocks.dedesignateHedge.mockResolvedValue(DEDESIGNATED);
}

/** Cambia el snapshot activo desde fuera de la pantalla, como lo haría el selector del Shell. */
function PickD1() {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId('D1')}>elegir D1</button>;
}

function renderScreen(path = '/coberturas/1') {
  return render(
    <SnapshotProvider>
      <PickD1 />
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/coberturas/:id" element={<HedgeScreen />} />
          <Route path="/coberturas" element={<div>lista</div>} />
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

describe('HedgeScreen', () => {
  it('carga la relación y la efectividad del snapshot activo, con la banda contable', async () => {
    setup();
    renderScreen();
    await screen.findByText('Flujo de efectivo');
    await screen.findByRole('heading', { name: 'Escenarios' });
    expect(mocks.getHedge).toHaveBeenCalledWith(1);
    expect(mocks.hedgeEffectiveness).toHaveBeenCalledWith(1, 'MX-DEMO');
    expect(screen.getByRole('note').textContent).toBe(NOTICE);
    expect(screen.getByText('Crédito a tasa variable')).toBeTruthy();
    expect(screen.getByText('50.00 %')).toBeTruthy();
    expect(screen.getByText('Activa')).toBeTruthy();
    expect(screen.getByText('Saldo de reserva')).toBeTruthy();
    expect(screen.getByRole('link', { name: /#8 · .* · Banco Alfa/ }).getAttribute('href')).toBe('/portafolio/8');
    expect(screen.getByText('Objetivo de gestión de riesgo')).toBeTruthy();
    expect(screen.getByText('Fijar el costo del crédito sindicado')).toBeTruthy();
  });

  it('recarga la efectividad al cambiar de snapshot', async () => {
    setup();
    renderScreen();
    await screen.findByRole('heading', { name: 'Escenarios' });
    expect(mocks.hedgeEffectiveness).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'elegir D1' }));
    await waitFor(() => expect(mocks.hedgeEffectiveness).toHaveBeenLastCalledWith(1, 'D1'));
    expect(mocks.hedgeEffectiveness).toHaveBeenCalledTimes(2);
    expect(mocks.getHedge).toHaveBeenCalledTimes(1);
  });

  it('rotula un término que no coincide y muestra "—" cuando la razón es nula', async () => {
    setup();
    renderScreen();
    const terms = await screen.findByRole('table', { name: 'Términos críticos' });
    const rows = within(terms).getAllByRole('row').slice(1);
    expect(rows[2].textContent).toContain('Vencimiento');
    expect(rows[2].textContent).toContain('No coincide');
    expect(rows[0].textContent).toContain('Coincide');

    const scen = screen.getByRole('table', { name: 'Escenarios' });
    const srows = within(scen).getAllByRole('row');
    expect(srows[1].textContent).toContain('1.0000');
    expect(srows[2].textContent).toContain('—');
    expect(screen.getByText('Relación económica: sí')).toBeTruthy();
    expect(screen.getByText('En 80 %–125 %: 1 de 1')).toBeTruthy();
    expect(screen.getByText(EFF.reference_note)).toBeTruthy();
  });

  it('un 409 de la efectividad se muestra como texto y no rompe la pantalla', async () => {
    setup();
    mocks.hedgeEffectiveness.mockRejectedValue(
      new ApiError(409, 'La operación ya no está viva al 2027-12-01', 'snapshot'),
    );
    renderScreen();
    expect(await screen.findByText('La operación ya no está viva al 2027-12-01')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Periodos' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Escenarios' })).toBeNull();
  });

  it('una cobertura de flujo de efectivo muestra las columnas de ORI y los asientos con su total', async () => {
    setup();
    renderScreen();
    const periods = await screen.findByRole('table', { name: 'Periodos' });
    for (const h of ['Δ ORI', 'Reciclaje', 'Saldo ORI']) {
      expect(within(periods).getByRole('columnheader', { name: h })).toBeTruthy();
    }
    expect(within(periods).queryByRole('columnheader', { name: 'Ajuste de partida' })).toBeNull();

    const journal = screen.getByRole('table', { name: 'Asientos 2026-12-15' });
    expect(within(journal).getAllByRole('row')).toHaveLength(6);
    const total = within(journal).getByText('Total del periodo').closest('tr')!;
    expect(total.textContent).toContain('MXN 156,000.00');
  });

  it('una cobertura de valor razonable no muestra columnas de ORI', async () => {
    setup(FAIR_VALUE_HEDGE);
    renderScreen();
    const periods = await screen.findByRole('table', { name: 'Periodos' });
    expect(within(periods).queryByRole('columnheader', { name: /ORI/ })).toBeNull();
    for (const h of ['Ajuste de partida', 'Inefectividad', 'Liquidado', 'Resultado del periodo']) {
      expect(within(periods).getByRole('columnheader', { name: h })).toBeTruthy();
    }
    const row = within(periods).getAllByRole('row')[1];
    expect(row.textContent).toContain('MXN 80,000.00');
    expect(row.textContent).toContain('MXN 5,000.00');
  });

  it('Cerrar periodo llama closeHedgePeriod con el snapshot elegido y recarga', async () => {
    setup();
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Cerrar periodo' });
    const select = within(form).getByLabelText('Snapshot del cierre') as HTMLSelectElement;
    expect(select.value).toBe('MX-DEMO');
    expect(within(form).getByRole('option', { name: 'Rodado · 2026-12-15' })).toBeTruthy();
    fireEvent.change(select, { target: { value: 'D1' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Cerrar periodo' }));

    await waitFor(() => expect(mocks.closeHedgePeriod).toHaveBeenCalledWith(1, 'D1'));
    await waitFor(() => expect(mocks.getHedge).toHaveBeenCalledTimes(2));
    expect(mocks.hedgeEffectiveness).toHaveBeenCalledTimes(2);
  });

  it('un error de Cerrar periodo con campo snapshot aparece bajo el select', async () => {
    setup();
    mocks.closeHedgePeriod.mockRejectedValue(new ApiError(409, 'El snapshot no es posterior al último cierre', 'snapshot'));
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Cerrar periodo' });
    fireEvent.click(within(form).getByRole('button', { name: 'Cerrar periodo' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toBe('El snapshot no es posterior al último cierre');
    expect(mocks.getHedge).toHaveBeenCalledTimes(1);
  });

  it('Desdesignar llama dedesignateHedge con la fecha y el motivo y recarga', async () => {
    setup();
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2027-01-10' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago del crédito' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));

    await waitFor(() =>
      expect(mocks.dedesignateHedge).toHaveBeenCalledWith(1, { date: '2027-01-10', reason: 'Prepago del crédito' }),
    );
    await waitFor(() => expect(mocks.getHedge).toHaveBeenCalledTimes(2));
  });

  it('Desdesignar sin motivo no llama al backend', async () => {
    setup();
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    expect((await within(form).findByRole('alert')).textContent).toBe('Indica el motivo');
    expect(mocks.dedesignateHedge).not.toHaveBeenCalled();
  });

  it('un error de Desdesignar con campo date aparece bajo la fecha', async () => {
    setup();
    mocks.dedesignateHedge.mockRejectedValue(new ApiError(409, 'La fecha es anterior al último cierre', 'date'));
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toBe('La fecha es anterior al último cierre');
    expect(within(form).getByLabelText('Fecha').getAttribute('aria-invalid')).toBe('true');
  });

  it('una relación desdesignada no muestra acciones y sí la reserva congelada con fecha y motivo', async () => {
    setup(DEDESIGNATED);
    renderScreen();
    await screen.findByText('Reserva congelada');
    expect(screen.getByText('Desdesignada')).toBeTruthy();
    expect(screen.getByText('2027-01-10')).toBeTruthy();
    expect(screen.getByText('Prepago del crédito')).toBeTruthy();
    expect(screen.queryByRole('form', { name: 'Cerrar periodo' })).toBeNull();
    expect(screen.queryByRole('form', { name: 'Desdesignar' })).toBeNull();
    expect(screen.queryByText('Saldo de reserva')).toBeNull();
  });

  it('el enlace de exportación apunta al CSV y la vista imprimible a su ruta', async () => {
    setup();
    renderScreen();
    const csv = await screen.findByRole('link', { name: 'Exportar asientos (CSV)' });
    expect(csv.getAttribute('href')).toBe('/api/hedges/1/report?format=csv');
    expect(csv.hasAttribute('download')).toBe(true);
    expect(screen.getByRole('link', { name: 'Vista imprimible' }).getAttribute('href')).toBe('/coberturas/1/reporte');
  });

  it('un id inválido muestra la banda contable y un aviso, sin llamar al backend', async () => {
    setup();
    renderScreen('/coberturas/abc');
    expect(await screen.findByText('Cobertura inválida')).toBeTruthy();
    expect(screen.getByRole('note').textContent).toBe(NOTICE);
    expect(mocks.getHedge).not.toHaveBeenCalled();
  });

  it('un error al cargar la relación se muestra como banda con la banda contable', async () => {
    setup();
    mocks.getHedge.mockRejectedValue(new ApiError(404, 'No existe la relación de cobertura', 'id'));
    renderScreen();
    expect(await screen.findByText('No existe la relación de cobertura')).toBeTruthy();
    expect(screen.getByRole('note').textContent).toBe(NOTICE);
  });
});
