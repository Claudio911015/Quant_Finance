import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { HedgeDetail, HedgeSummary, Snapshot, Trade } from '../api/types';
import { ApiError } from '../api/client';
import { SnapshotProvider } from '../state/SnapshotContext';
import HedgesScreen from './HedgesScreen';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  listHedges: vi.fn(),
  listTrades: vi.fn(),
  createHedge: vi.fn(),
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    listHedges: mocks.listHedges,
    listTrades: mocks.listTrades,
    createHedge: mocks.createHedge,
  };
});

const NOTICE =
  'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9';

const HEDGES: HedgeSummary[] = [
  {
    id: 1,
    trade_id: 8,
    product: 'irs',
    counterparty: 'Banco Alfa',
    hedge_type: 'cash_flow',
    item_kind: 'floating_loan',
    fraction: 0.5,
    hedge_ratio: 1,
    designation_date: '2026-11-10',
    status: 'activa',
    oci_balance: -125000,
    last_close: '2026-12-15',
    periods_count: 1,
  },
  {
    id: 2,
    trade_id: 9,
    product: 'irs',
    counterparty: 'Banco Beta',
    hedge_type: 'fair_value',
    item_kind: 'fixed_loan',
    fraction: 1,
    hedge_ratio: 1,
    designation_date: '2026-11-10',
    status: 'desdesignada',
    oci_balance: 0,
    last_close: null,
    periods_count: 0,
  },
];

const TRADES: Trade[] = [
  {
    id: 8,
    product: 'irs',
    counterparty: 'Banco Alfa',
    trade_date: '2026-11-10',
    start_date: '2026-11-10',
    maturity_date: '2027-11-09',
    params: {},
    notional: 500000000,
    currency: 'MXN',
    maturity: '2027-11-09',
    created_at: '2026-11-10T10:00:00',
  },
  {
    id: 9,
    product: 'fx_forward',
    counterparty: 'Banco Beta',
    trade_date: '2026-11-10',
    start_date: '2026-11-10',
    maturity_date: '2027-05-11',
    params: {},
    notional: 10000000,
    currency: 'USD',
    maturity: '2027-05-11',
    created_at: '2026-11-10T10:00:00',
  },
];

const DOC = {
  risk_management_objective: 'Fijar el costo del crédito',
  hedged_risk: 'Variabilidad de TIIE',
  effectiveness_method: 'Coincidencia de términos críticos y análisis de escenarios con derivado hipotético',
  ineffectiveness_sources: 'Diferencias de fechas',
};

function setup(hedges: HedgeSummary[] = HEDGES) {
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(
    async (id: string) => ({ id, as_of: '2026-11-10' }) as unknown as Snapshot,
  );
  mocks.listHedges.mockResolvedValue(hedges);
  mocks.listTrades.mockResolvedValue(TRADES);
  mocks.createHedge.mockResolvedValue({ id: 5, warnings: [] } as unknown as HedgeDetail);
}

function renderScreen() {
  return render(
    <SnapshotProvider>
      <MemoryRouter initialEntries={['/coberturas']}>
        <Routes>
          <Route path="/coberturas" element={<HedgesScreen />} />
          <Route path="/coberturas/:id" element={<div>detalle de cobertura</div>} />
        </Routes>
      </MemoryRouter>
    </SnapshotProvider>,
  );
}

/** Abre el formulario y espera a que la lista de operaciones llene el select. */
async function openForm() {
  fireEvent.click(await screen.findByRole('button', { name: 'Nueva relación' }));
  const form = await screen.findByRole('form', { name: 'Nueva relación de cobertura' });
  await within(form).findByRole('option', { name: /^#8 · / });
  return form;
}

function fillFloatingLoan(form: HTMLElement) {
  fireEvent.change(within(form).getByLabelText('Nocional'), { target: { value: '500,000,000' } });
  fireEvent.change(within(form).getByLabelText('Inicio'), { target: { value: '2026-11-10' } });
  fireEvent.change(within(form).getByLabelText('Vencimiento'), { target: { value: '2027-11-09' } });
  fireEvent.change(within(form).getByLabelText('Fracción'), { target: { value: '50' } });
  fireEvent.change(within(form).getByLabelText('Objetivo de gestión de riesgo'), {
    target: { value: DOC.risk_management_objective },
  });
  fireEvent.change(within(form).getByLabelText('Riesgo cubierto'), { target: { value: DOC.hedged_risk } });
  fireEvent.change(within(form).getByLabelText('Fuentes de inefectividad'), {
    target: { value: DOC.ineffectiveness_sources },
  });
}

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('HedgesScreen', () => {
  it('lista las relaciones con estado, último cierre y saldo de reserva', async () => {
    setup();
    renderScreen();
    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);

    const first = within(rows[0]).getAllByRole('cell');
    expect(within(first[0]).getByRole('link', { name: '1' }).getAttribute('href')).toBe('/coberturas/1');
    expect(within(first[1]).getByRole('link', { name: '#8 · Swap de tasas (IRS) · Banco Alfa' }).getAttribute('href')).toBe(
      '/portafolio/8',
    );
    expect(first[2].textContent).toBe('Flujo de efectivo');
    expect(first[3].textContent).toBe('Crédito a tasa variable');
    expect(first[4].textContent).toBe('50.00 %');
    expect(first[5].textContent).toBe('Activa');
    expect(first[6].textContent).toBe('2026-12-15');
    expect(first[7].textContent).toBe('MXN -125,000.00');

    const second = within(rows[1]).getAllByRole('cell');
    expect(second[2].textContent).toBe('Valor razonable');
    expect(second[5].textContent).toBe('Desdesignada');
    expect(second[6].textContent).toBe('—');
    expect(second[7].textContent).toBe('MXN 0.00');
  });

  it('sin relaciones dice "Sin relaciones de cobertura"', async () => {
    setup([]);
    renderScreen();
    await screen.findByText('Sin relaciones de cobertura');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('muestra la banda contable y el encabezado', async () => {
    setup();
    renderScreen();
    expect(screen.getByRole('heading', { name: 'Coberturas' })).toBeTruthy();
    expect(screen.getByRole('note').textContent).toBe(NOTICE);
    await screen.findByRole('table');
  });

  it('un fallo al listar se muestra como banda', async () => {
    setup();
    mocks.listHedges.mockRejectedValue(new ApiError(500, 'Error interno'));
    renderScreen();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Error interno');
  });

  it('el formulario floating_loan envía el cuerpo con la fracción en decimal y navega al detalle', async () => {
    setup();
    renderScreen();
    const form = await openForm();
    expect((within(form).getByLabelText('Operación') as HTMLSelectElement).value).toBe('8');
    expect((within(form).getByLabelText('Razón de cobertura') as HTMLInputElement).value).toBe('1');
    expect((within(form).getByLabelText('Método de efectividad') as HTMLTextAreaElement).value).toBe(
      'Coincidencia de términos críticos y análisis de escenarios con derivado hipotético',
    );
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    await waitFor(() =>
      expect(mocks.createHedge).toHaveBeenCalledWith({
        trade_id: 8,
        snapshot: 'MX-DEMO',
        hedge_type: 'cash_flow',
        item_kind: 'floating_loan',
        item_terms: {
          index: 'TIIE-F',
          notional: 500000000,
          start_date: '2026-11-10',
          maturity_date: '2027-11-09',
          side: 'pays_floating',
        },
        fraction: 0.5,
        hedge_ratio: 1,
        documentation: DOC,
      }),
    );
    await screen.findByText('detalle de cobertura');
  });

  it('si el alta trae avisos los muestra con un enlace a la cobertura, sin navegar', async () => {
    setup();
    mocks.createHedge.mockResolvedValue({
      id: 5,
      warnings: [
        { code: 'no_economic_relationship', message: 'La prueba prospectiva no muestra relación económica entre el instrumento y la partida' },
        { code: 'instrument_off_market', message: 'El instrumento vale MXN 12,500.00 al designar: ese valor ya está en libros y es fuente de inefectividad' },
      ],
    } as unknown as HedgeDetail);
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    const panel = await screen.findByRole('region', { name: 'Relación creada' });
    expect(within(panel).getByRole('heading', { name: 'Cobertura 5 creada con avisos' })).toBeTruthy();
    const items = within(panel).getAllByRole('listitem').map((li) => li.textContent);
    expect(items[0]).toContain('no muestra relación económica');
    expect(items[1]).toContain('fuente de inefectividad');
    expect(within(panel).getByRole('link', { name: 'Ver la cobertura 5' }).getAttribute('href')).toBe('/coberturas/5');
    expect(screen.queryByText('detalle de cobertura')).toBeNull();
    // El formulario se cierra y la lista se refresca para incluir la relación nueva.
    expect(screen.queryByRole('form', { name: 'Nueva relación de cobertura' })).toBeNull();
    await waitFor(() => expect(mocks.listHedges).toHaveBeenCalledTimes(2));
  });

  it('abrir de nuevo el formulario quita el panel de avisos de la relación anterior', async () => {
    setup();
    mocks.createHedge.mockResolvedValue({
      id: 5,
      warnings: [{ code: 'forecast_date_weekend', message: 'La fecha del flujo cae en fin de semana' }],
    } as unknown as HedgeDetail);
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));
    await screen.findByRole('region', { name: 'Relación creada' });
    fireEvent.click(screen.getByRole('button', { name: 'Nueva relación' }));
    expect(screen.queryByRole('region', { name: 'Relación creada' })).toBeNull();
    expect(await screen.findByRole('form', { name: 'Nueva relación de cobertura' })).toBeTruthy();
  });

  it('un 409 de designación anterior al último evento (campo snapshot) se muestra como banda del formulario', async () => {
    setup();
    mocks.createHedge.mockRejectedValue(
      new ApiError(409, 'La designación (2026-11-10) es anterior al último evento (2027-01-29) de la cobertura 3 de esta operación', 'snapshot'),
    );
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toContain('es anterior al último evento (2027-01-29) de la cobertura 3');
    expect(screen.queryByText('detalle de cobertura')).toBeNull();
  });

  it('cambiar la partida a forecast_fx muestra sus campos y quita los del crédito', async () => {
    setup();
    renderScreen();
    const form = await openForm();
    expect(within(form).getByLabelText('Índice')).toBeTruthy();
    fireEvent.change(within(form).getByLabelText('Partida'), { target: { value: 'forecast_fx' } });

    expect(within(form).queryByLabelText('Índice')).toBeNull();
    expect(within(form).queryByLabelText('Nocional')).toBeNull();
    expect(within(form).queryByLabelText('Inicio')).toBeNull();
    expect(within(form).queryByLabelText('Vencimiento')).toBeNull();
    expect(within(form).getByLabelText('Monto USD')).toBeTruthy();
    expect(within(form).getByLabelText('Fecha')).toBeTruthy();
    const side = within(form).getByLabelText('Lado') as HTMLSelectElement;
    expect(within(side).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Compra de USD',
      'Venta de USD',
    ]);

    fireEvent.change(within(form).getByLabelText('Operación'), { target: { value: '9' } });
    fireEvent.change(within(form).getByLabelText('Monto USD'), { target: { value: '10000000' } });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2027-05-11' } });
    fireEvent.change(side, { target: { value: 'sell_usd' } });
    fireEvent.change(within(form).getByLabelText('Objetivo de gestión de riesgo'), { target: { value: 'a' } });
    fireEvent.change(within(form).getByLabelText('Riesgo cubierto'), { target: { value: 'b' } });
    fireEvent.change(within(form).getByLabelText('Fuentes de inefectividad'), { target: { value: 'c' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    await waitFor(() => expect(mocks.createHedge).toHaveBeenCalledTimes(1));
    const body = mocks.createHedge.mock.calls[0][0];
    expect(body.trade_id).toBe(9);
    expect(body.item_kind).toBe('forecast_fx');
    expect(body.item_terms).toEqual({ amount_usd: 10000000, date: '2027-05-11', side: 'sell_usd' });
    expect(body.fraction).toBe(1);
  });

  it('elegir el tipo "Valor razonable" deja solo "Crédito a tasa fija" con lados Paga fija y Cobra fija', async () => {
    setup();
    renderScreen();
    const form = await openForm();
    fireEvent.change(within(form).getByLabelText('Tipo'), { target: { value: 'fair_value' } });

    const kind = within(form).getByLabelText('Partida') as HTMLSelectElement;
    expect(within(kind).getAllByRole('option').map((o) => o.textContent)).toEqual(['Crédito a tasa fija']);
    expect(kind.value).toBe('fixed_loan');
    const side = within(form).getByLabelText('Lado') as HTMLSelectElement;
    expect(within(side).getAllByRole('option').map((o) => o.textContent)).toEqual(['Paga fija', 'Cobra fija']);
    expect(side.value).toBe('pays_fixed');

    // Volver a flujo de efectivo elige la primera partida válida: crédito a tasa variable.
    fireEvent.change(within(form).getByLabelText('Tipo'), { target: { value: 'cash_flow' } });
    expect((within(form).getByLabelText('Partida') as HTMLSelectElement).value).toBe('floating_loan');
    expect((within(form).getByLabelText('Lado') as HTMLSelectElement).value).toBe('pays_floating');
  });

  it('un 409 con field "fraction" aparece bajo Fracción y no navega', async () => {
    setup();
    mocks.createHedge.mockRejectedValue(
      new ApiError(409, 'La suma de fracciones de la operación excede 100 %', 'fraction'),
    );
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    const input = within(form).getByLabelText('Fracción') as HTMLInputElement;
    await waitFor(() => expect(input.getAttribute('aria-invalid')).toBe('true'));
    const field = input.closest('.hedges__field') as HTMLElement;
    expect(within(field).getByRole('alert').textContent).toBe('La suma de fracciones de la operación excede 100 %');
    expect(screen.queryByText('detalle de cobertura')).toBeNull();
  });

  it('muestra los errores reales del backend con los nombres de la pantalla, no con claves en inglés', async () => {
    setup();
    mocks.createHedge.mockRejectedValue(
      new ApiError(400, "'maturity_date' debe ser posterior a 'start_date'", 'maturity_date'),
    );
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    const maturity = within(form).getByLabelText('Vencimiento') as HTMLInputElement;
    await waitFor(() => expect(maturity.getAttribute('aria-invalid')).toBe('true'));
    const field = maturity.closest('.hedges__field') as HTMLElement;
    expect(within(field).getByRole('alert').textContent).toBe('Vencimiento debe ser posterior a inicio');
  });

  it('una fracción fuera de 0–100 % se rechaza en la pantalla, en %, sin llamar al backend', async () => {
    setup();
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.change(within(form).getByLabelText('Fracción'), { target: { value: '150' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    const input = within(form).getByLabelText('Fracción') as HTMLInputElement;
    await waitFor(() => expect(input.getAttribute('aria-invalid')).toBe('true'));
    const field = input.closest('.hedges__field') as HTMLElement;
    expect(within(field).getByRole('alert').textContent).toBe('La fracción debe ser mayor que 0 % y no pasar de 100 %');
    expect(mocks.createHedge).not.toHaveBeenCalled();
  });

  it('un error de una clave de item_terms o de documentation va bajo su campo', async () => {
    setup();
    mocks.createHedge
      .mockRejectedValueOnce(new ApiError(400, 'El vencimiento debe ser posterior al inicio', 'maturity_date'))
      .mockRejectedValueOnce(new ApiError(400, 'Falta el riesgo cubierto', 'hedged_risk'));
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);

    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));
    const maturity = within(form).getByLabelText('Vencimiento') as HTMLInputElement;
    await waitFor(() => expect(maturity.getAttribute('aria-invalid')).toBe('true'));
    expect(
      within(maturity.closest('.hedges__field') as HTMLElement).getByRole('alert').textContent,
    ).toBe('El vencimiento debe ser posterior al inicio');

    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));
    const risk = within(form).getByLabelText('Riesgo cubierto') as HTMLTextAreaElement;
    await waitFor(() => expect(risk.getAttribute('aria-invalid')).toBe('true'));
    expect(maturity.getAttribute('aria-invalid')).toBeNull();
  });

  it('un error sin campo visible se muestra como banda', async () => {
    setup();
    mocks.createHedge.mockRejectedValue(new ApiError(404, 'No existe el snapshot', 'snapshot'));
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    await waitFor(() => expect(within(form).getByRole('alert').textContent).toBe('No existe el snapshot'));
    expect(form.querySelectorAll('[aria-invalid="true"]')).toHaveLength(0);
  });

  it('un número ilegible no se envía y se marca bajo su campo', async () => {
    setup();
    renderScreen();
    const form = await openForm();
    fillFloatingLoan(form);
    fireEvent.change(within(form).getByLabelText('Nocional'), { target: { value: 'abc' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Crear relación' }));

    const notional = within(form).getByLabelText('Nocional') as HTMLInputElement;
    await waitFor(() => expect(notional.getAttribute('aria-invalid')).toBe('true'));
    expect(mocks.createHedge).not.toHaveBeenCalled();
  });
});
