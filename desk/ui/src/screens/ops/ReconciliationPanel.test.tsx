import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Reconciliation, ReconciliationSummary } from '../../api/opsTypes';
import type { Trade } from '../../api/types';
import { ApiError } from '../../api/client';
import { ReconciliationPanel } from './ReconciliationPanel';

const mocks = vi.hoisted(() => ({
  createReconciliation: vi.fn(),
  listReconciliations: vi.fn(),
  getReconciliation: vi.fn(),
  listTrades: vi.fn(),
}));

vi.mock('../../api/opsClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/opsClient')>();
  return {
    ...actual,
    createReconciliation: mocks.createReconciliation,
    listReconciliations: mocks.listReconciliations,
    getReconciliation: mocks.getReconciliation,
  };
});

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, listTrades: mocks.listTrades };
});

vi.mock('../../state/SnapshotContext', () => ({
  useSnapshot: () => ({
    snapshotId: 'MX-DEMO',
    snapshot: { id: 'MX-DEMO', as_of: '2026-11-10' },
    snapshots: [],
  }),
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
    created_at: '2026-11-10T00:00:00+00:00',
  };
}

const TRADES = [
  trade(1, 'Banco Beta (sintético)'),
  trade(2, 'Banco Alfa (sintético)'),
  trade(3, 'Banco Alfa (sintético)'),
];

const SUMMARY = {
  matched: 4,
  conciliada: 1,
  explicable: 1,
  revisar: 2,
  bank_only: 1,
  own_only: 1,
  own_pv_mxn: -2500000,
  bank_pv_mxn: -2480000,
  difference_mxn: -20000,
};

const RUN: Reconciliation = {
  id: 7,
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  counterparty: 'Banco Alfa (sintético)',
  tolerance: 0.0001,
  created_at: '2026-11-11T18:00:00+00:00',
  disclaimer: 'La descomposición es una ayuda de diagnóstico, no una prueba.',
  summary: SUMMARY,
  rows: [
    {
      line: 2,
      trade_id: 2,
      bank_ref: null,
      product: 'irs',
      currency: 'MXN',
      notional_mxn: 5e8,
      own_pv_mxn: -1234500,
      bank_pv: -1234567.89,
      bank_currency: 'MXN',
      bank_pv_mxn: -1234567.89,
      difference_mxn: 67.89,
      difference_rel: 1.3578e-7,
      status: 'conciliada',
      decomposition: {
        date: { prev_date: '2026-11-09', next_date: '2026-11-11', pv_prev: -1240000, pv_next: -1229000, attributed: true },
        curve: { curve: 'TIIE-F', bp: 0.0068 },
        fx: null,
      },
      terms_flag: false,
      error: null,
    },
    {
      line: 3,
      trade_id: 3,
      bank_ref: 'BA-2026-0042',
      product: 'irs',
      currency: 'MXN',
      notional_mxn: 2.5e8,
      own_pv_mxn: 1000000,
      bank_pv: 1020000,
      bank_currency: 'MXN',
      bank_pv_mxn: 1020000,
      difference_mxn: -20000,
      difference_rel: -0.00008,
      status: 'explicable',
      decomposition: {
        date: { prev_date: '2026-11-09', next_date: '2026-11-11', pv_prev: 900000, pv_next: 1100000, attributed: false },
        curve: { curve: 'TIIE-F', bp: 5 },
        fx: null,
      },
      terms_flag: false,
      error: null,
    },
    {
      line: 4,
      trade_id: 5,
      bank_ref: null,
      product: 'fx_forward',
      currency: 'USD',
      notional_mxn: 1.9e8,
      own_pv_mxn: 3000000,
      bank_pv: 100000,
      bank_currency: 'USD',
      bank_pv_mxn: 1942000,
      difference_mxn: 1058000,
      difference_rel: 0.0056,
      status: 'revisar',
      decomposition: {
        date: { prev_date: '2026-11-09', next_date: '2026-11-11', pv_prev: 2900000, pv_next: 3100000, attributed: false },
        curve: null,
        fx: { spot: 19.42, pct: 1.2 },
      },
      terms_flag: true,
      error: null,
    },
    {
      line: 5,
      trade_id: 6,
      bank_ref: null,
      product: 'fx_option',
      currency: 'USD',
      notional_mxn: 1e8,
      own_pv_mxn: null,
      bank_pv: 50,
      bank_currency: 'MXN',
      bank_pv_mxn: 50,
      difference_mxn: null,
      difference_rel: null,
      status: 'revisar',
      decomposition: null,
      terms_flag: false,
      error: 'No se pudo valuar: vol fuera de superficie',
    },
  ],
  bank_only: [{ line: 6, trade_id: 999, bank_ref: null, bank_pv: 1000, currency: 'MXN', reason: 'Operación inexistente' }],
  own_only: [{ trade_id: 7, product: 'cap_floor', own_pv_mxn: 812345 }],
};

const HISTORY: ReconciliationSummary[] = [
  {
    id: 7,
    snapshot: 'MX-DEMO',
    as_of: '2026-11-10',
    counterparty: 'Banco Alfa (sintético)',
    tolerance: 0.0001,
    created_at: '2026-11-11T18:00:00+00:00',
    summary: SUMMARY,
  },
  {
    id: 5,
    snapshot: 'OTRO',
    as_of: '2026-10-10',
    counterparty: 'Banco Alfa (sintético)',
    tolerance: 0.0001,
    created_at: '2026-10-11T09:30:00+00:00',
    summary: { ...SUMMARY, conciliada: 3, explicable: 0, revisar: 0, matched: 3, bank_only: 0, own_only: 0 },
  },
];

function renderPanel() {
  return render(
    <MemoryRouter>
      <ReconciliationPanel />
    </MemoryRouter>,
  );
}

async function ready() {
  // Espera a que las contrapartes lleguen y el historial se consulte.
  await screen.findByRole('option', { name: 'Banco Alfa (sintético)' });
  await waitFor(() => expect(mocks.listReconciliations).toHaveBeenCalled());
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listTrades.mockResolvedValue(TRADES);
  mocks.listReconciliations.mockResolvedValue(HISTORY);
  mocks.getReconciliation.mockResolvedValue(RUN);
  mocks.createReconciliation.mockResolvedValue(RUN);
});

describe('ReconciliationPanel', () => {
  it('lista las contrapartes únicas y ordenadas, y consulta el historial de la primera', async () => {
    renderPanel();
    await ready();
    const select = screen.getByLabelText('Contraparte') as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      'Banco Alfa (sintético)',
      'Banco Beta (sintético)',
    ]);
    expect(select.value).toBe('Banco Alfa (sintético)');
    expect(mocks.listReconciliations).toHaveBeenCalledWith({ counterparty: 'Banco Alfa (sintético)' });
    expect(screen.getByTestId('recon-snapshot').textContent).toBe('MX-DEMO · 2026-11-10');
    expect((screen.getByLabelText('Tolerancia (% del nocional)') as HTMLInputElement).value).toBe('0.01');
    expect((screen.getByLabelText('CSV del banco') as HTMLTextAreaElement).placeholder).toContain('trade_id,bank_pv,currency,bank_ref');
  });

  it('enviar llama createReconciliation con la tolerancia como fracción', async () => {
    renderPanel();
    await ready();
    const csv = 'trade_id,bank_pv,currency,bank_ref\n2,-1234567.89,MXN,\n';
    fireEvent.change(screen.getByLabelText('CSV del banco'), { target: { value: csv } });
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });
    expect(mocks.createReconciliation).toHaveBeenCalledWith({
      snapshot: 'MX-DEMO',
      counterparty: 'Banco Alfa (sintético)',
      csv,
      tolerance: 0.0001,
    });
  });

  it('convierte otra tolerancia en % a fracción sin ruido de coma flotante', async () => {
    renderPanel();
    await ready();
    fireEvent.change(screen.getByLabelText('Tolerancia (% del nocional)'), { target: { value: '0.07' } });
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await waitFor(() => expect(mocks.createReconciliation).toHaveBeenCalled());
    expect(mocks.createReconciliation.mock.calls[0][0].tolerance).toBe(0.0007);
  });

  it('una tolerancia ilegible no llama al backend', async () => {
    renderPanel();
    await ready();
    fireEvent.change(screen.getByLabelText('Tolerancia (% del nocional)'), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    expect((await screen.findByRole('alert')).textContent).toContain('tolerancia');
    expect(mocks.createReconciliation).not.toHaveBeenCalled();
  });

  it('pinta resumen, las tres insignias de estado, la bandera de términos y el aviso', async () => {
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    const result = await screen.findByRole('region', { name: 'Resultado de la conciliación' });

    expect(within(result).getByTestId('recon-disclaimer').textContent).toBe(RUN.disclaimer);
    const summary = within(result).getByLabelText('Resumen');
    expect(within(summary).getByText('Solo en el banco').nextElementSibling?.textContent).toBe('1');
    expect(within(summary).getByText('PV propio').nextElementSibling?.textContent).toBe('MXN -2,500,000.00');
    expect(within(summary).getByText('Diferencia').nextElementSibling?.textContent).toBe('MXN -20,000.00');

    const table = within(result).getAllByRole('table')[0];
    expect(within(table).getByText('Conciliada')).toBeTruthy();
    expect(within(table).getByText('Explicable')).toBeTruthy();
    expect(within(table).getAllByText('Revisar')).toHaveLength(2);
    // La bandera solo está en la fila con terms_flag.
    const flagged = within(result).getAllByText('Revisar términos');
    expect(flagged).toHaveLength(1);
    expect(screen.getByTestId('recon-row-4').contains(flagged[0])).toBe(true);
  });

  it('muestra fecha, curva y tipo de cambio de la descomposición', async () => {
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });

    const r2 = within(screen.getByTestId('recon-row-2'));
    expect(r2.getByText('Atribuible')).toBeTruthy();
    expect(r2.getByText('+0.0 pb')).toBeTruthy();
    expect(r2.getByText('0.0000 %')).toBeTruthy();

    const r3 = within(screen.getByTestId('recon-row-3'));
    expect(r3.getByText('+5.0 pb')).toBeTruthy();
    expect(r3.queryByText('Atribuible')).toBeNull();
    expect(r3.getByText('BA-2026-0042', { exact: false })).toBeTruthy();

    const r4 = within(screen.getByTestId('recon-row-4'));
    expect(r4.getByText('19.42 (+1.20 %)')).toBeTruthy();
    expect(r4.getByText('Forward USD/MXN')).toBeTruthy();
    expect(r4.getByRole('link', { name: '#5' }).getAttribute('href')).toBe('/portafolio/5');
  });

  it('una fila con error de valuación no inventa cifras y muestra el mensaje', async () => {
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });
    const r5 = within(screen.getByTestId('recon-row-5'));
    expect(r5.getByText('No se pudo valuar: vol fuera de superficie')).toBeTruthy();
    expect(r5.getAllByText('—').length).toBeGreaterThanOrEqual(4);
  });

  it('lista "Solo en el banco" con su motivo y "Solo en QF Desk"', async () => {
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });

    const bank = within(screen.getByRole('region', { name: 'Solo en el banco' }));
    expect(bank.getByText('Operación inexistente')).toBeTruthy();
    expect(bank.getByText('#999')).toBeTruthy();

    const own = within(screen.getByRole('region', { name: 'Solo en QF Desk' }));
    expect(own.getByText('Cap / floor')).toBeTruthy();
    expect(own.getByRole('link', { name: '#7' }).getAttribute('href')).toBe('/portafolio/7');
    expect(own.getByText('812,345.00')).toBeTruthy();
  });

  it('el enlace de exportación apunta al CSV de la corrida', async () => {
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });
    expect(screen.getByRole('link', { name: 'Exportar CSV' }).getAttribute('href')).toBe(
      '/api/reconciliations/7?format=csv',
    );
  });

  it('cargar un archivo llena el área de texto', async () => {
    renderPanel();
    await ready();
    const text = 'trade_id,bank_pv,currency,bank_ref\n2,10,MXN,\n';
    const file = new File([text], 'banco.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('Archivo CSV'), { target: { files: [file] } });
    await waitFor(() => expect((screen.getByLabelText('CSV del banco') as HTMLTextAreaElement).value).toBe(text));
  });

  it('un ApiError 400 del CSV muestra su mensaje tal cual y no deja resultado', async () => {
    mocks.createReconciliation.mockRejectedValue(new ApiError(400, "Línea 3: 'bank_pv' no es un número finito", 'csv'));
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    expect((await screen.findByRole('alert')).textContent).toBe("Línea 3: 'bank_pv' no es un número finito");
    expect(screen.queryByRole('region', { name: 'Resultado de la conciliación' })).toBeNull();
  });

  it('el historial muestra fecha, snapshot y conteos; elegir una corrida llama getReconciliation(id)', async () => {
    renderPanel();
    await ready();
    const history = await screen.findByRole('region', { name: 'Historial de conciliaciones' });
    const items = within(history).getAllByRole('button');
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain('2026-11-11 18:00 UTC');
    expect(items[0].textContent).toContain('MX-DEMO');
    expect(items[0].textContent).toContain('1 conciliadas');
    expect(items[1].textContent).toContain('OTRO');

    fireEvent.click(items[1]);
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });
    expect(mocks.getReconciliation).toHaveBeenCalledWith(5);
  });

  it('cambiar de contraparte consulta su historial y limpia el resultado anterior', async () => {
    renderPanel();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar' }));
    await screen.findByRole('region', { name: 'Resultado de la conciliación' });

    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: 'Banco Beta (sintético)' } });
    await waitFor(() =>
      expect(mocks.listReconciliations).toHaveBeenLastCalledWith({ counterparty: 'Banco Beta (sintético)' }),
    );
    expect(screen.queryByRole('region', { name: 'Resultado de la conciliación' })).toBeNull();
  });

  it('sin historial lo dice', async () => {
    mocks.listReconciliations.mockResolvedValue([]);
    renderPanel();
    await ready();
    expect(await screen.findByText('Sin conciliaciones guardadas para esta contraparte.')).toBeTruthy();
  });

  it('un fallo al listar operaciones muestra el mensaje del backend', async () => {
    mocks.listTrades.mockRejectedValue(new ApiError(500, 'Base no disponible'));
    renderPanel();
    expect((await screen.findByRole('alert')).textContent).toBe('Base no disponible');
    expect((screen.getByRole('button', { name: 'Conciliar' }) as HTMLButtonElement).disabled).toBe(true);
  });
});
