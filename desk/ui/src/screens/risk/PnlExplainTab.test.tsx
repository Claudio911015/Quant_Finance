import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { ExplainResponse, ExplainStepKey } from '../../api/riskTypes';
import type { Snapshot, SnapshotSummary } from '../../api/types';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { productTitle } from '../pricers/registry';
import { PnlExplainTab, cascadeOption } from './PnlExplainTab';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  pnlExplain: vi.fn(),
}));

// echarts pinta en canvas, que jsdom no tiene; aquí solo importa qué opción recibe la gráfica.
interface ChartProps {
  option: unknown;
  ariaLabel?: string;
}
const charts: ChartProps[] = [];
vi.mock('../../components/EChart', () => ({
  cssColor: (token: string) => token,
  EChart: (props: ChartProps) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, listSnapshots: mocks.listSnapshots, getSnapshot: mocks.getSnapshot };
});

vi.mock('../../api/riskClient', () => ({ pnlExplain: mocks.pnlExplain }));

const STEPS = [
  { key: 'carry', label: 'Paso del tiempo y liquidaciones' },
  { key: 'curve:TIIE-F', label: 'Tasas TIIE-F' },
  { key: 'curve:SOFR', label: 'Tasas SOFR' },
  { key: 'fx', label: 'Tipo de cambio' },
  { key: 'vol', label: 'Volatilidad' },
  { key: 'new_trades', label: 'Operaciones nuevas' },
  { key: 'events', label: 'Eventos' },
  { key: 'residual', label: 'Residuo' },
] as const;

function components(values: Partial<Record<ExplainStepKey, number>>): Record<ExplainStepKey, number> {
  const out: Record<string, number> = {};
  for (const s of STEPS) out[s.key] = values[s.key] ?? 0;
  return out as Record<ExplainStepKey, number>;
}

const EXPLAIN: ExplainResponse = {
  from: { snapshot: 'MX-DEMO', as_of: '2026-11-10' },
  to: { snapshot: 'D1', as_of: '2026-12-10' },
  steps: [...STEPS],
  totals: {
    pnl: -812345.12,
    components: components({ carry: 120000, 'curve:TIIE-F': -950000, 'curve:SOFR': 3000, fx: 14654.88 }),
  },
  rows: [
    {
      id: 1,
      product: 'irs',
      counterparty: 'Banco Alfa (sintético)',
      pnl: -400000,
      components: components({ carry: 50000, 'curve:TIIE-F': -450000 }),
      error: null,
      explain_error: null,
      warnings: [],
    },
    {
      id: 2,
      product: 'fx_forward',
      counterparty: 'Banco Beta (sintético)',
      pnl: null,
      components: null,
      error: 'Sin cotización USDMXN',
      explain_error: null,
      warnings: [],
    },
    {
      id: 3,
      product: 'cap_floor',
      counterparty: 'Banco Gamma (sintético)',
      pnl: 1500,
      components: components({ residual: 1500 }),
      error: null,
      explain_error: 'curva sin pilares',
      warnings: [],
    },
  ],
};

function summary(id: string, asOf: string): SnapshotSummary {
  return { id, label: id, synthetic: true, as_of: asOf, data_quality: 'synthetic', sources: {} } as unknown as SnapshotSummary;
}

const MX = summary('MX-DEMO', '2026-11-10');
const D1 = summary('D1', '2026-12-10');
const MID = summary('MID', '2026-11-25');

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderTab() {
  return render(
    <SnapshotProvider>
      <SwitchTo id="MX-DEMO" />
      <PnlExplainTab />
    </SnapshotProvider>,
  );
}

const desde = () => screen.getByLabelText('Desde') as HTMLSelectElement;
const hasta = () => screen.getByLabelText('Hasta') as HTMLSelectElement;

beforeEach(() => {
  window.history.replaceState(null, '', '/riesgo?tab=pnl');
  charts.length = 0;
  // El primero de la lista es el snapshot activo (no hay MKT-LIVE): D1 es el más reciente.
  mocks.listSnapshots.mockResolvedValue([D1, MX]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.pnlExplain.mockResolvedValue(EXPLAIN);
});

afterEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, '', '/');
});

describe('PnlExplainTab: selección de snapshots', () => {
  it('por omisión Hasta es el snapshot actual y Desde el de mayor as_of anterior', async () => {
    mocks.listSnapshots.mockResolvedValue([D1, MX, MID]);
    renderTab();

    await screen.findByRole('table');
    expect(hasta().value).toBe('D1');
    expect(desde().value).toBe('MID');
    expect(mocks.pnlExplain).toHaveBeenCalledWith('MID', 'D1');
    expect(within(desde()).getByRole('option', { name: 'MX-DEMO · 2026-11-10' })).toBeTruthy();
  });

  it('sin snapshot anterior, Desde es el actual y Hasta el siguiente posterior', async () => {
    mocks.listSnapshots.mockResolvedValue([MX, MID, D1]);
    renderTab();

    await screen.findByRole('table');
    expect(desde().value).toBe('MX-DEMO');
    expect(hasta().value).toBe('MID');
    expect(mocks.pnlExplain).toHaveBeenCalledWith('MX-DEMO', 'MID');
  });

  it('con un solo snapshot avisa que hacen falta dos y no calcula', async () => {
    mocks.listSnapshots.mockResolvedValue([MX]);
    renderTab();

    expect(await screen.findByText('Se necesitan dos snapshots')).toBeTruthy();
    await waitFor(() => expect(mocks.getSnapshot).toHaveBeenCalled());
    expect(mocks.pnlExplain).not.toHaveBeenCalled();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('?from= y ?to= de la URL inicial tienen prioridad sobre los valores por omisión', async () => {
    window.history.replaceState(null, '', '/riesgo?tab=pnl&from=D1&to=MX-DEMO');
    renderTab();

    await screen.findByRole('table');
    expect(desde().value).toBe('D1');
    expect(hasta().value).toBe('MX-DEMO');
    expect(mocks.pnlExplain).toHaveBeenCalledWith('D1', 'MX-DEMO');
  });

  it('un id de la URL que no es un snapshot conocido se ignora', async () => {
    window.history.replaceState(null, '', '/riesgo?tab=pnl&from=NOEXISTE');
    renderTab();

    await screen.findByRole('table');
    expect(desde().value).toBe('MX-DEMO');
    expect(mocks.pnlExplain).toHaveBeenCalledWith('MX-DEMO', 'D1');
  });

  it('cambiar Desde vuelve a llamar a pnlExplain con el valor nuevo', async () => {
    mocks.listSnapshots.mockResolvedValue([D1, MX, MID]);
    renderTab();
    await screen.findByRole('table');
    expect(mocks.pnlExplain).toHaveBeenCalledTimes(1);

    fireEvent.change(desde(), { target: { value: 'MX-DEMO' } });

    await waitFor(() => expect(mocks.pnlExplain).toHaveBeenLastCalledWith('MX-DEMO', 'D1'));
    expect(mocks.pnlExplain).toHaveBeenCalledTimes(2);
  });

  it('cambiar el snapshot activo recalcula mientras no se haya elegido a mano', async () => {
    mocks.listSnapshots.mockResolvedValue([D1, MX, MID]);
    renderTab();
    await screen.findByRole('table');

    fireEvent.click(screen.getByRole('button', { name: 'cambiar a MX-DEMO' }));

    await waitFor(() => expect(mocks.pnlExplain).toHaveBeenLastCalledWith('MX-DEMO', 'MID'));
  });

  it('el 400 del backend sobre "to" aparece bajo Hasta', async () => {
    mocks.pnlExplain.mockRejectedValue(new ApiError(400, 'El snapshot "from" es posterior a "to"', 'to'));
    renderTab();

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('El snapshot "from" es posterior a "to"');
    expect(hasta().getAttribute('aria-invalid')).toBe('true');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('un error sin campo se muestra como aviso general', async () => {
    mocks.pnlExplain.mockRejectedValue(new ApiError(404, 'No existe el snapshot', 'snapshot'));
    renderTab();

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('No existe el snapshot');
    expect(desde().getAttribute('aria-invalid')).toBeNull();
    expect(hasta().getAttribute('aria-invalid')).toBeNull();
  });
});

describe('PnlExplainTab: tabla por operación', () => {
  it('las columnas siguen el orden de steps', async () => {
    renderTab();
    await screen.findByRole('table');

    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent);
    expect(headers).toEqual(['ID', 'Producto', 'Contraparte', 'P&L', ...STEPS.map((s) => s.label)]);
  });

  it('cada operación muestra su P&L y un importe por paso', async () => {
    renderTab();
    await screen.findByRole('table');

    const row = screen.getByText('Banco Alfa (sintético)').closest('tr')!;
    const cells = within(row).getAllByRole('cell').map((c) => c.textContent);
    expect(cells.slice(0, 3)).toEqual(['1', productTitle('irs'), 'Banco Alfa (sintético)']);
    expect(cells.slice(3)).toEqual([
      'MXN -400,000',
      'MXN 50,000',
      'MXN -450,000',
      'MXN 0',
      'MXN 0',
      'MXN 0',
      'MXN 0',
      'MXN 0',
      'MXN 0',
    ]);
  });

  it('la fila de totales trae el P&L oficial y el total de cada paso', async () => {
    renderTab();
    await screen.findByRole('table');

    const total = screen.getByRole('rowheader', { name: 'Total' }).closest('tr')!;
    const cells = within(total).getAllByRole('cell').map((c) => c.textContent);
    expect(cells).toEqual([
      'MXN -812,345',
      'MXN 120,000',
      'MXN -950,000',
      'MXN 3,000',
      'MXN 14,655',
      'MXN 0',
      'MXN 0',
      'MXN 0',
      'MXN 0',
    ]);
  });

  it('muestra pesos enteros y deja el importe con centavos en el title de la celda', async () => {
    renderTab();
    await screen.findByRole('table');

    const total = screen.getByRole('rowheader', { name: 'Total' }).closest('tr')!;
    const cells = within(total).getAllByRole('cell');
    expect(cells[0].textContent).toBe('MXN -812,345');
    expect(cells[0].getAttribute('title')).toBe('MXN -812,345.12');
    expect(cells[4].getAttribute('title')).toBe('MXN 14,654.88');
  });

  it('una fila con error muestra el error en una celda que abarca los pasos', async () => {
    renderTab();
    await screen.findByRole('table');

    const row = screen.getByText('Banco Beta (sintético)').closest('tr')!;
    const err = within(row).getByText('Sin cotización USDMXN');
    expect(err.getAttribute('colspan')).toBe(String(STEPS.length));
    expect(within(row).getAllByRole('cell')).toHaveLength(5);
  });

  it('explain_error aparece como nota bajo la fila y su P&L queda en el residuo', async () => {
    renderTab();
    await screen.findByRole('table');

    const note = screen.getByText(/todo su P&L va al residuo: curva sin pilares/);
    expect(note.getAttribute('role')).toBe('status');
    const row = screen.getByText('Banco Gamma (sintético)').closest('tr')!;
    const cells = within(row).getAllByRole('cell').map((c) => c.textContent);
    expect(cells[3]).toBe('MXN 1,500');
    expect(cells[cells.length - 1]).toBe('MXN 1,500');
  });

  it('el pie recuerda que la suma de pasos y residuo es el P&L y que el orden importa', async () => {
    renderTab();
    await screen.findByRole('table');

    expect(
      screen.getByText(
        'La suma de los pasos más el residuo es el P&L de la pestaña P&L; el orden de la cascada importa (ver Metodología). Importes en pesos enteros; el detalle con centavos aparece al pasar el cursor.',
      ),
    ).toBeTruthy();
  });
});

describe('PnlExplainTab: gráfica', () => {
  it('monta la cascada con su etiqueta accesible y 9 barras', async () => {
    renderTab();
    await screen.findByRole('table');

    expect(screen.getByRole('img', { name: 'Cascada del P&L explicado' })).toBeTruthy();
    const last = charts[charts.length - 1];
    expect(last.ariaLabel).toBe('Cascada del P&L explicado');
    const opt = last.option as { xAxis: { data: string[] } };
    expect(opt.xAxis.data).toEqual([...STEPS.map((s) => s.label), 'P&L total']);
  });
});

interface Series {
  data: (number | { value: number; itemStyle: { color: string } })[];
}
interface WaterfallOption {
  xAxis: { data: string[] };
  series: Series[];
}

const values = (s: Series) => s.data.map((d) => (typeof d === 'number' ? d : d.value));
const colors = (s: Series) => s.data.map((d) => (typeof d === 'number' ? null : d.itemStyle.color));

describe('cascadeOption', () => {
  it('arma 9 barras: una por paso en el orden de steps y la del P&L total', () => {
    const opt = cascadeOption(EXPLAIN) as unknown as WaterfallOption;

    expect(opt.xAxis.data).toHaveLength(9);
    expect(opt.xAxis.data[0]).toBe('Paso del tiempo y liquidaciones');
    expect(opt.xAxis.data[8]).toBe('P&L total');
    expect(opt.series).toHaveLength(3);
    for (const s of opt.series) expect(s.data).toHaveLength(9);
  });

  it('flota cada barra entre el acumulado anterior y el posterior, también al cruzar el cero', () => {
    const res: ExplainResponse = {
      ...EXPLAIN,
      totals: {
        pnl: 150,
        components: components({ carry: 100, 'curve:TIIE-F': -300, 'curve:SOFR': -50, fx: 400 }),
      },
    };
    const [base, up, down] = (cascadeOption(res) as unknown as WaterfallOption).series;

    // acumulados: 0 → 100 → -200 → -250 → 150 → (150 sin cambio hasta el residuo) y total 0 → 150
    expect(values(base)).toEqual([0, 0, -200, 0, 150, 150, 150, 150, 0]);
    expect(values(up)).toEqual([100, 100, 0, 150, 0, 0, 0, 0, 150]);
    expect(values(down)).toEqual([0, -200, -50, -250, 0, 0, 0, 0, 0]);
  });

  it('pinta por signo: positivos con --pos y negativos con --neg, incluida la barra total', () => {
    const [, up] = (cascadeOption(EXPLAIN) as unknown as WaterfallOption).series;

    // carry +120000, TIIE-F -950000, SOFR +3000, fx +14654.88, el resto 0 (cuenta como positivo), total -812345.12
    expect(colors(up)).toEqual([
      '--pos',
      '--neg',
      '--pos',
      '--pos',
      '--pos',
      '--pos',
      '--pos',
      '--pos',
      '--neg',
    ]);
  });

  it('el alto visible de cada barra es el valor absoluto del paso', () => {
    const [, up, down] = (cascadeOption(EXPLAIN) as unknown as WaterfallOption).series;
    const heights = values(up).map((u, i) => u - values(down)[i]);

    const expected = [
      ...STEPS.map((s) => Math.abs(EXPLAIN.totals.components[s.key])),
      Math.abs(EXPLAIN.totals.pnl),
    ];
    heights.forEach((h, i) => expect(h).toBeCloseTo(expected[i], 6));
  });
});
