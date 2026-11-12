import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { INCREMENTAL_FIXTURE, XVA_FIXTURE } from './fixtures';
import { IncrementalPanel } from './IncrementalPanel';

const mocks = vi.hoisted(() => ({ xvaIncremental: vi.fn(), createTrade: vi.fn() }));
vi.mock('../../api/xvaClient', () => ({ xvaIncremental: mocks.xvaIncremental }));
vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, createTrade: mocks.createTrade };
});

const charts: { option: { series?: { name?: string; data: unknown[] }[] }; ariaLabel?: string }[] = [];
vi.mock('../../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: (typeof charts)[number]) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

const NAMES = XVA_FIXTURE.counterparties.map((c) => c.counterparty);

const input = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const calculate = () => fireEvent.click(screen.getByRole('button', { name: 'Calcular' }));

function renderPanel(onTraded = vi.fn()) {
  render(<IncrementalPanel snapshotId="MX-DEMO" counterparties={NAMES} onTraded={onTraded} />);
  return onTraded;
}

beforeEach(() => {
  charts.length = 0;
  mocks.xvaIncremental.mockResolvedValue(INCREMENTAL_FIXTURE);
  mocks.createTrade.mockResolvedValue({ id: 12 });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('IncrementalPanel: captura', () => {
  it('ofrece las contrapartes y solo los dos productos que cubre el XVA, con su rótulo', () => {
    renderPanel();
    expect(within(screen.getByLabelText('Contraparte')).getAllByRole('option').map((o) => o.textContent)).toEqual(NAMES);
    expect(within(screen.getByLabelText('Producto')).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Swap de tasas (IRS)',
      'Cross currency swap USDMXN',
    ]);
  });

  it('usa los campos del pricer del producto elegido', () => {
    renderPanel();
    expect(input('Nocional').value).toBe('100,000,000');
    expect(screen.getByLabelText('Tasa fija')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Producto'), { target: { value: 'xccy_swap' } });
    expect(screen.queryByLabelText('Tasa fija')).toBeNull();
    expect(input('Nocional USD').value).toBe('10,000,000');
    expect(screen.getByLabelText('Diferencial sobre TIIE-F')).toBeTruthy();
  });

  it('no calcula con un campo obligatorio vacío', () => {
    renderPanel();
    fireEvent.change(input('Nocional'), { target: { value: '' } });
    calculate();
    expect(screen.getByRole('alert').textContent).toBe('Campo obligatorio');
    expect(mocks.xvaIncremental).not.toHaveBeenCalled();
  });
});

describe('IncrementalPanel: cálculo', () => {
  it('envía snapshot, contraparte, producto y parámetros convertidos', async () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: NAMES[1] } });
    fireEvent.change(input('Tasa fija'), { target: { value: '7.1' } });
    calculate();
    await screen.findByRole('table', { name: 'XVA antes y después' });
    expect(mocks.xvaIncremental).toHaveBeenCalledWith({
      snapshot: 'MX-DEMO',
      counterparty: NAMES[1],
      product: 'irs',
      params: { curve: 'TIIE-F', side: 'payer', notional: 100000000, periods: 13, fixed_rate: 0.071 },
    });
  });

  it('muestra antes, después e incremental por componente, en MXN y en pb', async () => {
    renderPanel();
    calculate();
    const table = await screen.findByRole('table', { name: 'XVA antes y después' });
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Componente',
      'Antes (MXN)',
      'Después (MXN)',
      'Incremental (MXN)',
      'Incremental (pb)',
    ]);
    const rows = within(table).getAllByRole('row').slice(1);
    const cells = (i: number) => within(rows[i]).getAllByRole('cell').map((c) => c.textContent);
    expect(cells(0)).toEqual(['CVA', 'MXN 120,000.00', 'MXN 123,500.00', 'MXN 3,500.00', '0.350']);
    expect(cells(1)).toEqual(['DVA', 'MXN 30,000.00', 'MXN 30,100.00', 'MXN 100.00', '0.010']);
    expect(cells(2)).toEqual(['FVA', 'MXN 5,000.00', 'MXN 5,020.00', 'MXN 20.00', '0.002']);
    expect(cells(3)).toEqual(['XVA total', 'MXN 95,000.00', 'MXN 98,420.00', 'MXN 3,420.00', '0.342']);
  });

  it('resume la candidata con su rótulo en español y superpone el perfil antes y después', async () => {
    renderPanel();
    calculate();
    await screen.findByRole('table', { name: 'XVA antes y después' });
    expect(screen.getByText(/^Candidata:.*Swap de tasas \(IRS\)/)).toBeTruthy();
    expect(screen.queryByText('irs')).toBeNull();
    expect(screen.queryByText('xccy_swap')).toBeNull();
    const chart = charts[charts.length - 1];
    expect(chart.ariaLabel).toBe('EPE y ENE antes y después de la operación');
    expect(chart.option.series!.map((s) => s.name)).toEqual(['EPE antes', 'EPE después', 'ENE antes', 'ENE después']);
  });

  it.each([
    [new ApiError(400, 'notional debe ser mayor que 0', 'notional'), 'Nocional'],
    [new ApiError(400, 'periods debe ser un entero mayor que 0', 'periods'), 'Periodos'],
  ])('un 400 con field se muestra junto al campo %#', async (error, label) => {
    mocks.xvaIncremental.mockRejectedValue(error);
    renderPanel();
    calculate();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(error.message);
    expect(input(label).getAttribute('aria-describedby')).toBe(alert.id);
  });

  it('un 404 de contraparte se muestra junto al selector de contraparte', async () => {
    mocks.xvaIncremental.mockRejectedValue(new ApiError(404, 'Contraparte inexistente: X', 'counterparty'));
    renderPanel();
    calculate();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Contraparte inexistente: X');
    expect(screen.getByLabelText('Contraparte').getAttribute('aria-describedby')).toBe(alert.id);
  });

  it('un 400 de producto se muestra junto al selector de producto', async () => {
    mocks.xvaIncremental.mockRejectedValue(new ApiError(400, 'El XVA incremental solo cubre swaps', 'product'));
    renderPanel();
    calculate();
    const alert = await screen.findByRole('alert');
    expect(screen.getByLabelText('Producto').getAttribute('aria-describedby')).toBe(alert.id);
  });

  it('un error sin campo conocido va en un aviso general', async () => {
    mocks.xvaIncremental.mockRejectedValue(new ApiError(400, 'La operación no está viva', 'trade_date'));
    renderPanel();
    calculate();
    expect((await screen.findByRole('alert')).textContent).toBe('La operación no está viva');
  });

  it('al fallar un cálculo se descarta el resultado anterior', async () => {
    renderPanel();
    calculate();
    await screen.findByRole('table', { name: 'XVA antes y después' });
    mocks.xvaIncremental.mockRejectedValue(new ApiError(400, 'notional debe ser mayor que 0', 'notional'));
    calculate();
    await screen.findByRole('alert');
    expect(screen.queryByRole('table', { name: 'XVA antes y después' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Pactar' })).toBeNull();
  });
});

describe('IncrementalPanel: pactar', () => {
  it('pacta con el mismo cuerpo que se calculó y pide recargar el XVA', async () => {
    const onTraded = renderPanel();
    fireEvent.change(screen.getByLabelText('Contraparte'), { target: { value: NAMES[2] } });
    calculate();
    await screen.findByRole('table', { name: 'XVA antes y después' });
    // editar el formulario después de calcular no cambia lo que se pacta
    fireEvent.change(input('Nocional'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Pactar' }));

    await waitFor(() => expect(onTraded).toHaveBeenCalledTimes(1));
    const sent = mocks.xvaIncremental.mock.calls[0][0];
    expect(mocks.createTrade).toHaveBeenCalledWith(sent);
    expect(sent.counterparty).toBe(NAMES[2]);
    expect(screen.getByRole('status').textContent).toContain('Operación #12 pactada');
    // el antes ya no es el mismo: el resultado se retira
    expect(screen.queryByRole('table', { name: 'XVA antes y después' })).toBeNull();
  });

  it('un error al pactar se muestra y no recarga', async () => {
    mocks.createTrade.mockRejectedValue(new ApiError(400, 'La fecha de vencimiento es inválida', 'maturity_date'));
    const onTraded = renderPanel();
    calculate();
    await screen.findByRole('table', { name: 'XVA antes y después' });
    fireEvent.click(screen.getByRole('button', { name: 'Pactar' }));
    expect((await screen.findByRole('alert')).textContent).toBe('La fecha de vencimiento es inválida');
    expect(onTraded).not.toHaveBeenCalled();
    expect(screen.getByRole('table', { name: 'XVA antes y después' })).toBeTruthy();
  });
});
