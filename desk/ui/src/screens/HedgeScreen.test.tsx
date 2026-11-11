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
  releaseHedgeReserve: vi.fn(),
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
    releaseHedgeReserve: mocks.releaseHedgeReserve,
  };
});

const SNAPSHOTS = [
  { id: 'MX-DEMO', label: 'Demo MX', as_of: '2026-11-10' },
  { id: 'D1', label: 'Rodado', as_of: '2026-12-15' },
  { id: 'D2', label: 'Rodado 2', as_of: '2027-01-25' },
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
    inst_total: -94000,
    hypo_total: -94000,
    effective_cum: -94000,
    settled_period: 31000,
    hypo_settled_period: 31000,
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
  warnings: [],
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
  dedesignation: {
    date: '2027-01-10',
    reason: 'Prepago del crédito',
    cause: 'instrument_ended',
    snapshot: 'D1',
    frozen_oci: -125000,
  },
};

const RELEASE_ENTRIES = [
  { account: 'ORI — reserva de cobertura', debit: 0, credit: 40000, memo: 'Liberación de la reserva de cobertura congelada' },
  { account: 'Resultados — partida cubierta (reciclaje)', debit: 40000, credit: 0, memo: 'Reciclaje de la reserva congelada: el flujo cubierto ocurrió' },
];

/** Desdesignada con una liberación parcial ya hecha: quedan 85,000 de los 125,000 congelados. */
const PARTLY_RELEASED: HedgeDetail = {
  ...DEDESIGNATED,
  oci_balance: -85000,
  events: [
    {
      id: 9,
      relationship_id: 1,
      type: 'reserve_release',
      event_date: '2027-01-20',
      created_at: '2027-01-20T10:00:00+00:00',
      data: {
        snapshot: 'D1',
        cause: 'flow_occurred',
        amount: -40000,
        reserve_before: -125000,
        reserve_after: -85000,
        entries: RELEASE_ENTRIES,
      },
    },
  ],
};

const FULLY_RELEASED: HedgeDetail = { ...PARTLY_RELEASED, oci_balance: 0 };

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
  mocks.releaseHedgeReserve.mockResolvedValue(PARTLY_RELEASED);
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
    expect(select.value).toBe('D2'); // el primero posterior al último cierre (2026-12-15), no el snapshot de la barra
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

  it('Desdesignar llama dedesignateHedge con snapshot, motivo y causa y recarga', async () => {
    setup();
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    const snap = within(form).getByLabelText('Snapshot de la desdesignación') as HTMLSelectElement;
    expect(snap.value).toBe('D2');
    fireEvent.change(snap, { target: { value: 'D1' } });
    fireEvent.change(within(form).getByLabelText('Causa'), { target: { value: 'criteria_not_met' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago del crédito' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));

    await waitFor(() =>
      expect(mocks.dedesignateHedge).toHaveBeenCalledWith(1, {
        snapshot: 'D1',
        reason: 'Prepago del crédito',
        cause: 'criteria_not_met',
      }),
    );
    await waitFor(() => expect(mocks.getHedge).toHaveBeenCalledTimes(2));
  });

  it('la causa de desdesignar ofrece las tres de IFRS 9 y no hay fecha libre', async () => {
    setup();
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    const cause = within(form).getByLabelText('Causa') as HTMLSelectElement;
    expect(cause.value).toBe('');
    expect(within(cause).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Elige la causa',
      'El instrumento venció, se vendió o se terminó',
      'La relación deja de cumplir los criterios',
      'Cambió el objetivo de gestión de riesgo',
    ]);
    expect(within(form).queryByLabelText('Fecha')).toBeNull();
    expect(form.querySelector('input[type="date"]')).toBeNull();
  });

  it('Desdesignar sin causa ni motivo no llama al backend y marca ambos campos', async () => {
    setup();
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    const alerts = await within(form).findAllByRole('alert');
    expect(alerts.map((a) => a.textContent)).toEqual(['Indica la causa', 'Indica el motivo']);
    expect(mocks.dedesignateHedge).not.toHaveBeenCalled();
  });

  it('un error de Desdesignar con campo snapshot aparece bajo el select y ofrece el snapshot del último cierre', async () => {
    setup();
    mocks.dedesignateHedge.mockRejectedValue(
      new ApiError(409, 'El snapshot (2026-12-01) no puede ser anterior a 2026-12-15, fecha del último cierre', 'snapshot'),
    );
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Causa'), { target: { value: 'instrument_ended' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toContain('no puede ser anterior a 2026-12-15');
    const snap = within(form).getByLabelText('Snapshot de la desdesignación') as HTMLSelectElement;
    expect(snap.getAttribute('aria-invalid')).toBe('true');

    fireEvent.click(within(form).getByRole('button', { name: 'Usar el snapshot del último cierre (D1)' }));
    expect(snap.value).toBe('D1');
    expect(within(form).queryByRole('button', { name: /Usar el snapshot/ })).toBeNull();
  });

  it('sin cierres, el snapshot que se ofrece tras un 409 es el de la designación', async () => {
    setup({ ...HEDGE, periods: [], last_close: null });
    mocks.dedesignateHedge.mockRejectedValue(new ApiError(409, 'El snapshot es anterior a la designación', 'snapshot'));
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Snapshot de la desdesignación'), { target: { value: 'D1' } });
    fireEvent.change(within(form).getByLabelText('Causa'), { target: { value: 'instrument_ended' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    await within(form).findByRole('alert');
    expect(
      within(form).getByRole('button', { name: 'Usar el snapshot de la designación (MX-DEMO)' }),
    ).toBeTruthy();
  });

  it('Desdesignar con el mensaje real del backend muestra el nombre del campo, no la clave', async () => {
    setup();
    mocks.dedesignateHedge.mockRejectedValue(new ApiError(400, "'reason' no puede estar vacío", 'reason'));
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Causa'), { target: { value: 'instrument_ended' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toBe('Motivo no puede estar vacío');
  });

  it('un 409 de Desdesignar sin campo visible (ya desdesignada) se muestra como banda de acciones', async () => {
    setup();
    mocks.dedesignateHedge.mockRejectedValue(new ApiError(409, 'La cobertura ya está desdesignada', 'id'));
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Causa'), { target: { value: 'instrument_ended' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    const acciones = screen.getByRole('region', { name: 'Acciones' });
    expect((await within(acciones).findByText('La cobertura ya está desdesignada')).getAttribute('role')).toBe('alert');
    expect(within(form).queryByRole('alert')).toBeNull();
  });

  it('los errores de un formulario se borran al usar el otro', async () => {
    setup();
    mocks.closeHedgePeriod.mockRejectedValue(new ApiError(409, 'El snapshot no es posterior al último cierre', 'snapshot'));
    renderScreen();
    const close = await screen.findByRole('form', { name: 'Cerrar periodo' });
    const ded = screen.getByRole('form', { name: 'Desdesignar' });

    // Error local en Desdesignar...
    fireEvent.click(within(ded).getByRole('button', { name: 'Desdesignar' }));
    await within(ded).findAllByRole('alert');
    // ...se borra al enviar Cerrar periodo, que a su vez deja el suyo.
    fireEvent.click(within(close).getByRole('button', { name: 'Cerrar periodo' }));
    await within(close).findByRole('alert');
    expect(within(ded).queryByRole('alert')).toBeNull();

    // Volver a usar Desdesignar borra el error de Cerrar periodo.
    fireEvent.focus(within(ded).getByLabelText('Motivo'));
    await waitFor(() => expect(within(close).queryByRole('alert')).toBeNull());
  });

  it('el aviso de una acción fallida (banda) se borra al usar otro formulario', async () => {
    setup();
    mocks.closeHedgePeriod.mockRejectedValue(new ApiError(500, 'Error interno', null));
    renderScreen();
    const close = await screen.findByRole('form', { name: 'Cerrar periodo' });
    fireEvent.click(within(close).getByRole('button', { name: 'Cerrar periodo' }));
    expect(await screen.findByText('Error interno')).toBeTruthy();
    fireEvent.focus(screen.getByLabelText('Motivo'));
    await waitFor(() => expect(screen.queryByText('Error interno')).toBeNull());
  });

  it('una relación desdesignada no muestra acciones y sí la reserva congelada con fecha y motivo', async () => {
    setup(DEDESIGNATED);
    renderScreen();
    await screen.findByText('Reserva congelada');
    expect(screen.getByText('Desdesignada')).toBeTruthy();
    expect(screen.getByText('2027-01-10')).toBeTruthy();
    expect(screen.getByText('Prepago del crédito')).toBeTruthy();
    expect(screen.getByText('El instrumento venció, se vendió o se terminó')).toBeTruthy();
    expect(screen.queryByRole('form', { name: 'Cerrar periodo' })).toBeNull();
    expect(screen.queryByRole('form', { name: 'Desdesignar' })).toBeNull();
    expect(screen.queryByText('Saldo de reserva')).toBeNull();
  });

  it('una desdesignación anterior a la causa obligatoria no rotula causa', async () => {
    setup({
      ...DEDESIGNATED,
      dedesignation: { date: '2027-01-10', reason: 'Prepago', cause: null, snapshot: null, frozen_oci: -125000 },
    });
    renderScreen();
    await screen.findByText('Reserva congelada');
    expect(screen.queryByText('Causa')).toBeNull();
  });

  it('una desdesignada con saldo muestra congelada, vigente y el formulario Liberar reserva', async () => {
    setup(PARTLY_RELEASED);
    renderScreen();
    await screen.findByText('Reserva congelada');
    const facts = screen.getByText('Reserva congelada').closest('dl')!;
    expect(within(facts).getByText('MXN -125,000.00')).toBeTruthy();
    expect(within(facts).getByText('Reserva vigente')).toBeTruthy();
    expect(within(facts).getByText('MXN -85,000.00')).toBeTruthy();
    const form = screen.getByRole('form', { name: 'Liberar reserva' });
    expect(within(form).getByText('Vacío libera todo el saldo (MXN -85,000.00)')).toBeTruthy();
    const cause = within(form).getByLabelText('Causa de la liberación') as HTMLSelectElement;
    expect(within(cause).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Elige la causa',
      'El flujo cubierto ocurrió',
      'El flujo cubierto ya no se espera',
    ]);
  });

  it('Liberar reserva sin monto libera todo el saldo con el snapshot y la causa elegidos', async () => {
    setup(PARTLY_RELEASED);
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Snapshot de la liberación'), { target: { value: 'D1' } });
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_no_longer_expected' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));

    await waitFor(() =>
      expect(mocks.releaseHedgeReserve).toHaveBeenCalledWith(1, { snapshot: 'D1', cause: 'flow_no_longer_expected' }),
    );
    expect(Object.keys(mocks.releaseHedgeReserve.mock.calls[0][1])).not.toContain('amount');
    await waitFor(() => expect(mocks.getHedge).toHaveBeenCalledTimes(2));
  });

  it('Liberar reserva con monto lo envía con el signo del saldo, aunque se teclee sin signo', async () => {
    setup(PARTLY_RELEASED); // saldo -85,000
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_occurred' } });
    fireEvent.change(within(form).getByLabelText('Monto a liberar'), { target: { value: '25,000.50' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    await waitFor(() =>
      expect(mocks.releaseHedgeReserve).toHaveBeenCalledWith(1, {
        snapshot: 'D2',
        cause: 'flow_occurred',
        amount: -25000.5,
      }),
    );
  });

  it('con saldo positivo el monto liberado también lleva el signo del saldo', async () => {
    setup({ ...PARTLY_RELEASED, oci_balance: 60000 });
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_occurred' } });
    fireEvent.change(within(form).getByLabelText('Monto a liberar'), { target: { value: '-10000' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    await waitFor(() =>
      expect(mocks.releaseHedgeReserve).toHaveBeenCalledWith(1, {
        snapshot: 'D2',
        cause: 'flow_occurred',
        amount: 10000,
      }),
    );
  });

  it('Liberar reserva sin causa o con un monto ilegible no llama al backend', async () => {
    setup(PARTLY_RELEASED);
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Monto a liberar'), { target: { value: 'mucho' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    const alerts = await within(form).findAllByRole('alert');
    expect(alerts.map((a) => a.textContent)).toEqual(['Indica la causa', 'Indica un número']);
    expect(mocks.releaseHedgeReserve).not.toHaveBeenCalled();
  });

  it('los errores del backend al liberar van bajo su campo, con el nombre de la pantalla', async () => {
    setup(PARTLY_RELEASED);
    mocks.releaseHedgeReserve.mockRejectedValue(
      new ApiError(409, 'El monto excede el saldo de la reserva (-85000.00)', 'amount'),
    );
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_occurred' } });
    fireEvent.change(within(form).getByLabelText('Monto a liberar'), { target: { value: '999999' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toBe('El monto excede el saldo de la reserva (-85000.00)');
    expect(within(form).getByLabelText('Monto a liberar').getAttribute('aria-invalid')).toBe('true');
  });

  it('un 409 al liberar por snapshot anterior al último evento aparece bajo el select', async () => {
    setup(PARTLY_RELEASED);
    mocks.releaseHedgeReserve.mockRejectedValue(
      new ApiError(409, 'El snapshot (2027-01-01) no puede ser anterior al último evento de la cobertura (2027-01-20)', 'snapshot'),
    );
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_occurred' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    expect((await within(form).findByRole('alert')).textContent).toContain('anterior al último evento');
    expect(within(form).getByLabelText('Snapshot de la liberación').getAttribute('aria-invalid')).toBe('true');
  });

  it('con la reserva liberada por completo no hay formulario y el asiento de la liberación aparece', async () => {
    setup(FULLY_RELEASED);
    renderScreen();
    await screen.findByText('Reserva congelada');
    expect(screen.queryByRole('form', { name: 'Liberar reserva' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Acciones' })).toBeNull();
    const table = screen.getByRole('table', { name: 'Asientos de liberación 2027-01-20' });
    expect(within(table).getByText('ORI — reserva de cobertura')).toBeTruthy();
    expect(within(table).getByText('Resultados — partida cubierta (reciclaje)')).toBeTruthy();
    const total = within(table).getByText('Total de la liberación').closest('tr')!;
    expect(total.textContent).toContain('MXN 40,000.00');
    expect(screen.getByText('Liberación de reserva al 2027-01-20')).toBeTruthy();
    expect(screen.getByText(/El flujo cubierto ocurrió · Monto MXN -40,000.00 · Reserva restante MXN -85,000.00/)).toBeTruthy();
  });

  it('una relación activa no ofrece Liberar reserva', async () => {
    setup();
    renderScreen();
    await screen.findByRole('form', { name: 'Desdesignar' });
    expect(screen.queryByRole('form', { name: 'Liberar reserva' })).toBeNull();
  });

  it('los avisos de la designación se muestran en el detalle, y sin avisos no hay bloque', async () => {
    setup({
      ...HEDGE,
      warnings: [
        { code: 'instrument_off_market', message: 'El instrumento vale MXN 12,500.00 al designar: ese valor ya está en libros y es fuente de inefectividad' },
        { code: 'forecast_date_weekend', message: 'La fecha del flujo cae en fin de semana: se liquidará con el spot del snapshot' },
      ],
    });
    const { unmount } = renderScreen();
    const block = await screen.findByRole('region', { name: 'Avisos de designación' });
    const items = within(block).getAllByRole('listitem').map((li) => li.textContent);
    expect(items[0]).toContain('vale MXN 12,500.00 al designar');
    expect(items[1]).toContain('fin de semana');
    unmount();

    setup();
    renderScreen();
    await screen.findByRole('heading', { name: 'Escenarios' });
    expect(screen.queryByRole('region', { name: 'Avisos de designación' })).toBeNull();
  });

  it('el término Sentido de un crédito rotula el lado del swap y el de la partida', async () => {
    setup();
    mocks.hedgeEffectiveness.mockResolvedValue({
      ...EFF,
      critical_terms: [
        ...EFF.critical_terms,
        { term: 'side', label: 'Sentido', instrument: 'receiver', item: 'pays_floating', result: 'mismatch' },
      ],
    });
    renderScreen();
    const terms = await screen.findByRole('table', { name: 'Términos críticos' });
    const row = within(terms).getAllByRole('row').slice(1)[3];
    expect(row.textContent).toContain('Sentido');
    expect(row.textContent).toContain('Cobra fija');
    expect(row.textContent).toContain('Paga variable');
    expect(row.textContent).toContain('No coincide');
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
  it('Cerrar periodo y Desdesignar arrancan en el primer snapshot con fecha posterior al último cierre', async () => {
    setup();
    mocks.listSnapshots.mockResolvedValue([
      { id: 'D2', label: 'Rodado 2', as_of: '2027-01-25' },
      { id: 'MX-DEMO', label: 'Demo MX', as_of: '2026-11-10' },
      { id: 'D3', label: 'Rodado 3', as_of: '2027-03-01' },
      { id: 'D1', label: 'Rodado', as_of: '2026-12-15' },
    ]);
    renderScreen();
    const close = await screen.findByRole('form', { name: 'Cerrar periodo' });
    expect((within(close).getByLabelText('Snapshot del cierre') as HTMLSelectElement).value).toBe('D2');
    const ded = screen.getByRole('form', { name: 'Desdesignar' });
    expect((within(ded).getByLabelText('Snapshot de la desdesignación') as HTMLSelectElement).value).toBe('D2');
  });

  it('sin cierres arranca en el primer snapshot posterior a la designación', async () => {
    setup({ ...HEDGE, periods: [], last_close: null });
    renderScreen();
    const close = await screen.findByRole('form', { name: 'Cerrar periodo' });
    expect((within(close).getByLabelText('Snapshot del cierre') as HTMLSelectElement).value).toBe('D1');
  });

  it('si no hay snapshot posterior al último cierre el selector queda vacío con una nota y no llama al backend', async () => {
    setup();
    mocks.listSnapshots.mockResolvedValue(SNAPSHOTS.slice(0, 2)); // el último es el del cierre (2026-12-15)
    renderScreen();
    const close = await screen.findByRole('form', { name: 'Cerrar periodo' });
    expect((within(close).getByLabelText('Snapshot del cierre') as HTMLSelectElement).value).toBe('');
    expect(within(close).getByText(/No hay ningún snapshot con fecha posterior a 2026-12-15/)).toBeTruthy();
    fireEvent.click(within(close).getByRole('button', { name: 'Cerrar periodo' }));
    expect((await within(close).findByRole('alert')).textContent).toBe('Indica el snapshot');
    expect(mocks.closeHedgePeriod).not.toHaveBeenCalled();

    const ded = screen.getByRole('form', { name: 'Desdesignar' });
    expect(within(ded).getByText(/No hay ningún snapshot con fecha posterior a 2026-12-15/)).toBeTruthy();
    fireEvent.change(within(ded).getByLabelText('Causa'), { target: { value: 'criteria_not_met' } });
    fireEvent.change(within(ded).getByLabelText('Motivo'), { target: { value: 'x' } });
    fireEvent.click(within(ded).getByRole('button', { name: 'Desdesignar' }));
    expect((await within(ded).findAllByRole('alert')).map((a) => a.textContent)).toEqual(['Indica el snapshot']);
    expect(mocks.dedesignateHedge).not.toHaveBeenCalled();
    fireEvent.change(within(ded).getByLabelText('Snapshot de la desdesignación'), { target: { value: 'D1' } }); // el del cierre sí
    expect(within(ded).queryByText(/No hay ningún snapshot/)).toBeNull();
  });

  it('Liberar reserva arranca en el primer snapshot que no es anterior al último evento', async () => {
    setup(PARTLY_RELEASED); // última liberación: 2027-01-20
    mocks.listSnapshots.mockResolvedValue([
      ...SNAPSHOTS,
      { id: 'D0', label: 'Del día', as_of: '2027-01-20' },
    ]);
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    expect((within(form).getByLabelText('Snapshot de la liberación') as HTMLSelectElement).value).toBe('D0');
  });

  it('una relación concluida se rotula, no admite cierres ni desdesignar, explica la reserva y permite liberarla', async () => {
    setup({
      ...HEDGE,
      status: 'concluida',
      oci_balance: 2500000,
      periods: [period({ trade_status: 'vencida', oci: 2500000 })],
      events: [
        { id: 2, relationship_id: 1, type: 'period_close', event_date: '2026-12-15', data: {}, created_at: '2026-12-15T10:00:00+00:00' },
      ],
    });
    renderScreen();
    expect(await screen.findByText('Concluida')).toBeTruthy();
    expect(screen.getByText(/Instrumento vencido antes que la partida/)).toBeTruthy();
    expect(screen.getByText('Saldo de reserva')).toBeTruthy();
    expect(screen.queryByRole('form', { name: 'Cerrar periodo' })).toBeNull();
    expect(screen.queryByRole('form', { name: 'Desdesignar' })).toBeNull();
    const form = screen.getByRole('form', { name: 'Liberar reserva' });
    expect(within(form).getByText('Vacío libera todo el saldo (MXN 2,500,000.00)')).toBeTruthy();
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_occurred' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    await waitFor(() =>
      expect(mocks.releaseHedgeReserve).toHaveBeenCalledWith(1, { snapshot: 'D1', cause: 'flow_occurred' }), // el cierre final
    );
  });

  it('una relación concluida sin reserva no ofrece acciones ni nota', async () => {
    setup({ ...HEDGE, status: 'concluida', oci_balance: 0, periods: [period({ trade_status: 'vencida', oci: 0 })] });
    renderScreen();
    expect(await screen.findByText('Concluida')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Acciones' })).toBeNull();
    expect(screen.queryByText(/Instrumento vencido antes que la partida/)).toBeNull();
  });

  it('muestra la fecha de designación y la de documentación, y el aviso de una cobertura documentada tarde', async () => {
    setup({
      ...HEDGE,
      created_at: '2026-11-14T09:30:00+00:00',
      warnings: [
        {
          code: 'designation_backdated',
          message: 'La cobertura se documenta el 2026-11-14, 4 días después de su fecha de designación (2026-11-10)',
        },
      ],
    });
    renderScreen();
    const facts = (await screen.findByText('Documentada el')).closest('dl')!;
    expect(within(facts).getByText('Designación').nextElementSibling!.textContent).toBe('2026-11-10');
    expect(within(facts).getByText('Documentada el').nextElementSibling!.textContent).toBe('2026-11-14');
    const block = screen.getByRole('region', { name: 'Avisos de designación' });
    expect(within(block).getByText(/se documenta el 2026-11-14, 4 días después/)).toBeTruthy();
  });
  it('un 409 de causa contrastada al desdesignar aparece bajo el campo Causa', async () => {
    setup();
    mocks.dedesignateHedge.mockRejectedValue(
      new ApiError(
        409,
        'La operación sigue viva al 2027-01-25: la causa «El instrumento venció, se vendió o se terminó» solo aplica si ya no lo está',
        'cause',
      ),
    );
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Desdesignar' });
    fireEvent.change(within(form).getByLabelText('Causa'), { target: { value: 'instrument_ended' } });
    fireEvent.change(within(form).getByLabelText('Motivo'), { target: { value: 'Prepago' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Desdesignar' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toContain('sigue viva al 2027-01-25');
    expect(within(form).getByLabelText('Causa').getAttribute('aria-invalid')).toBe('true');
  });

  it('un 409 de causa contrastada al liberar aparece bajo el campo de la causa', async () => {
    setup(PARTLY_RELEASED);
    mocks.releaseHedgeReserve.mockRejectedValue(
      new ApiError(
        409,
        'El flujo cubierto aún no ocurre al 2027-01-25 (su primera fecha es 2027-03-01): si ya no se espera, la causa es «El flujo cubierto ya no se espera»',
        'cause',
      ),
    );
    renderScreen();
    const form = await screen.findByRole('form', { name: 'Liberar reserva' });
    fireEvent.change(within(form).getByLabelText('Causa de la liberación'), { target: { value: 'flow_occurred' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Liberar reserva' }));
    expect((await within(form).findByRole('alert')).textContent).toContain('su primera fecha es 2027-03-01');
    expect(within(form).getByLabelText('Causa de la liberación').getAttribute('aria-invalid')).toBe('true');
  });
});
