import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { XvaSensitivitiesResponse } from '../../api/xvaTypes';
import { fmtMoney, fmtNumber } from '../../lib/format';
import { XVA_SENSITIVITIES_FIXTURE as FIXTURE } from './fixtures';
import { XvaSensitivitiesPanel, sensitivityOption } from './XvaSensitivitiesPanel';

const mocks = vi.hoisted(() => ({ getXvaSensitivities: vi.fn() }));
vi.mock('../../api/xvaClient', () => ({ getXvaSensitivities: mocks.getXvaSensitivities }));

type Chart = { option: { xAxis?: { data: string[] }; series?: { name?: string; type?: string; data: unknown[] }[] }; ariaLabel?: string };
const charts: Chart[] = [];
vi.mock('../../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: Chart) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

const ALFA = FIXTURE.counterparty;
const money = (v: number) => fmtMoney(v, 'MXN');
const plain = (v: number) => fmtNumber(v, 2);
const four = (r: { cva: number; dva: number; fva: number; total: number }) => [r.cva, r.dva, r.fva, r.total];
const click = () => fireEvent.click(screen.getByRole('button', { name: 'Calcular sensibilidades' }));
const curvesTable = () => screen.getByRole('table', { name: 'Sensibilidad por curva y pilar' });
const factorsTable = () =>
  screen.getByRole('table', { name: 'Sensibilidad a tipo de cambio, volatilidades, crédito y fondeo' });

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** La fila de una tabla cuya primera celda es `label`, dentro del grupo (tbody) cuyo título es `group` (seguido,
 * si lo trae, de « · unidad»). */
function rowIn(table: HTMLElement, group: string, label: string): HTMLElement {
  const title = new RegExp(`^${escape(group)}(?:\\s*·|$)`);
  const body = within(table)
    .getAllByRole('rowgroup')
    .find((rg) => within(rg).queryByRole('rowheader', { name: title }) !== null && rg.tagName === 'TBODY');
  if (!body) throw new Error(`sin grupo ${group}`);
  return within(body).getByRole('row', { name: new RegExp(`^${label}(?:\\s|$)`) });
}

const cellsOf = (row: HTMLElement) => within(row).getAllByRole('cell').map((c) => c.textContent);

function renderPanel(counterparty = ALFA, snapshotId = 'MX-DEMO') {
  return render(<XvaSensitivitiesPanel snapshotId={snapshotId} counterparty={counterparty} />);
}

beforeEach(() => {
  charts.length = 0;
  mocks.getXvaSensitivities.mockResolvedValue(FIXTURE);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('XvaSensitivitiesPanel: petición', () => {
  it('no pide nada al montar y el botón llama una vez con el snapshot y la contraparte', async () => {
    renderPanel();
    expect(mocks.getXvaSensitivities).not.toHaveBeenCalled();
    click();
    expect(mocks.getXvaSensitivities).toHaveBeenCalledTimes(1);
    expect(mocks.getXvaSensitivities).toHaveBeenCalledWith('MX-DEMO', ALFA);
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
  });

  it('avisa antes de calcular que puede tardar decenas de segundos', () => {
    renderPanel();
    expect(screen.getByText(/pueden tardar decenas de segundos en conjuntos largos/)).toBeTruthy();
    expect(screen.getByText(/tiempo real y lo que habría tardado por choques/)).toBeTruthy();
    expect(screen.queryByText(/^Calculando las sensibilidades/)).toBeNull();
  });

  it('muestra «Calculando…» con el botón deshabilitado y el aviso de espera mientras la promesa no resuelve', async () => {
    let resolve: (r: XvaSensitivitiesResponse) => void = () => {};
    mocks.getXvaSensitivities.mockReturnValue(new Promise<XvaSensitivitiesResponse>((r) => (resolve = r)));
    renderPanel();
    click();
    const busy = screen.getByRole('button', { name: 'Calculando…' }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(screen.getByText(/^Calculando las sensibilidades: puede tardar decenas de segundos/)).toBeTruthy();
    resolve(FIXTURE);
    const again = (await screen.findByRole('button', { name: 'Calcular sensibilidades' })) as HTMLButtonElement;
    expect(again.disabled).toBe(false);
  });

  it('un error (p. ej. 501 sin XAD) muestra el texto de la API y ninguna tabla', async () => {
    const msg = 'Sensibilidades no disponibles: el motor se compiló sin XAD (QF_WITH_XAD=OFF)';
    mocks.getXvaSensitivities.mockRejectedValue(new ApiError(501, msg));
    renderPanel();
    click();
    expect((await screen.findByRole('alert')).textContent).toBe(msg);
    expect(screen.queryByRole('table')).toBeNull();
    expect((screen.getByRole('button', { name: 'Calcular sensibilidades' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('un fallo de red se muestra como falta de conexión', async () => {
    mocks.getXvaSensitivities.mockRejectedValue(new Error('boom'));
    renderPanel();
    click();
    expect((await screen.findByRole('alert')).textContent).toBe('No se pudo conectar con el backend');
  });

  it('al cambiar de contraparte se limpia el resultado y una respuesta en vuelo se descarta', async () => {
    let resolve: (r: XvaSensitivitiesResponse) => void = () => {};
    const { rerender } = renderPanel();
    click();
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
    rerender(<XvaSensitivitiesPanel snapshotId="MX-DEMO" counterparty="Banco Beta (sintético)" />);
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Sensibilidades de Banco Beta (sintético)' })).toBeTruthy();

    mocks.getXvaSensitivities.mockReturnValue(new Promise<XvaSensitivitiesResponse>((r) => (resolve = r)));
    click();
    rerender(<XvaSensitivitiesPanel snapshotId="MX-DEMO" counterparty={ALFA} />);
    resolve(FIXTURE);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Calcular sensibilidades' })).toBeTruthy());
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('al cambiar de snapshot también se limpia', async () => {
    const { rerender } = renderPanel();
    click();
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
    rerender(<XvaSensitivitiesPanel snapshotId="OTRO" counterparty={ALFA} />);
    expect(screen.queryByRole('table')).toBeNull();
  });
});

describe('XvaSensitivitiesPanel: resultado', () => {
  beforeEach(async () => {
    renderPanel();
    click();
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
  });

  it('tabla por curva y pilar con la parcial y la total (MXN-USD recalibrada), y el DV01 paralelo de cada curva', () => {
    const table = curvesTable();
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Pilar',
      'Parcial (MXN-USD fija)',
      'Total (MXN-USD recalibrada)',
      ...['CVA', 'DVA', 'FVA', 'Total', 'CVA', 'DVA', 'FVA', 'Total'],
    ]);
    expect(within(table).getAllByRole('rowheader', { name: /^(TIIE-F|SOFR|MXN-USD)$/ })).toHaveLength(3);
    const tiie = FIXTURE.curves[0];
    expect(tiie.pillars).toHaveLength(10);
    const p = tiie.pillars[4];
    expect(p.recalibrated).toBeDefined();
    expect(p.recalibrated?.cva).not.toBe(p.cva);
    expect(cellsOf(rowIn(table, 'TIIE-F', p.label))).toEqual([...four(p), ...four(p.recalibrated!)].map(plain));
    for (const c of FIXTURE.curves.slice(0, 2)) {
      expect(cellsOf(rowIn(table, c.curve, 'DV01 paralelo'))).toEqual([...four(c.dv01), ...four(c.dv01.recalibrated!)].map(plain));
    }
    expect(within(table).getAllByRole('row', { name: /^DV01 paralelo/ })).toHaveLength(3);
  });

  it('MXN-USD, que es lo que se recalibra, muestra su parcial y «—» donde iría la total', () => {
    const mxn = FIXTURE.curves[2];
    expect(mxn.curve).toBe('MXN-USD');
    expect(mxn.pillars.some((p) => p.recalibrated)).toBe(false);
    expect(cellsOf(rowIn(curvesTable(), 'MXN-USD', mxn.pillars[3].label))).toEqual([...four(mxn.pillars[3]).map(plain), '—']);
  });

  it('dice cuál usar para cubrir: la total', () => {
    expect(screen.getByText(/^Para cubrir con instrumentos de TIIE-F, de SOFR o del tipo de cambio, use la total/)).toBeTruthy();
  });

  it('indica la unidad de las curvas y la de cada grupo de factores (tipo de cambio, volatilidades, CDS, intensidad, fondeo)', () => {
    expect(screen.getByRole('heading', { name: 'Curvas de tasas (MXN por pb)' })).toBeTruthy();
    const groups = within(factorsTable())
      .getAllByRole('rowheader')
      .map((h) => h.textContent)
      .filter((t) => t?.includes(' · '));
    expect(groups).toEqual([
      'Tipo de cambio · MXN por 1 % del spot',
      'Volatilidades · MXN por punto (vol USDMXN), por pb de vol normal (σ Hull-White), por 0.01 (a)',
      `Crédito de ${ALFA} · MXN por pb de cotización de CDS`,
      'Crédito propio · MXN por pb de intensidad',
      'Fondeo · MXN por pb',
    ]);
    const { xva } = FIXTURE;
    expect(screen.getByText(/^XVA de la contraparte:/).textContent).toContain(`CVA ${money(xva.cva_mxn)}`);
  });

  it('filas de tipo de cambio, volatilidades, CDS por plazo propios y de la contraparte, y fondeo', () => {
    const table = factorsTable();
    const fx = FIXTURE.fx;
    expect(cellsOf(rowIn(table, 'Tipo de cambio', 'USDMXN spot, parcial \\(MXN-USD fija\\)'))).toEqual(four(fx).map(money));
    expect(cellsOf(rowIn(table, 'Tipo de cambio', 'USDMXN spot, total \\(MXN-USD recalibrada\\)'))).toEqual(
      four(fx.recalibrated!).map(money),
    );
    for (const v of FIXTURE.vols) {
      expect(cellsOf(rowIn(table, 'Volatilidades', v.label))).toEqual([v.cva, v.dva, v.fva, v.total].map(money));
    }
    const cds = FIXTURE.credit.counterparty.cds;
    expect(cds).toHaveLength(6);
    for (const c of cds) {
      expect(cellsOf(rowIn(table, `Crédito de ${ALFA}`, `CDS ${c.tenor}`))).toEqual([c.cva, c.dva, c.fva, c.total].map(money));
    }
    const f = FIXTURE.funding;
    expect(cellsOf(rowIn(table, 'Fondeo', 'Diferencial de fondeo'))).toEqual([f.cva, f.dva, f.fva, f.total].map(money));
  });

  it('el crédito propio sin CDS (supuesto) muestra la intensidad de su tramo único', () => {
    const h = FIXTURE.credit.own.hazards[0];
    expect(cellsOf(rowIn(factorsTable(), 'Crédito propio', 'Intensidad \\(tramo único\\)'))).toEqual(
      [h.cva, h.dva, h.fva, h.total].map(money),
    );
  });

  it('muestra los supuestos, el método y el costo medido frente a los choques', () => {
    expect(screen.getByText(/^Un pilar o plazo en cero queda más allá del último vencimiento/)).toBeTruthy();
    expect(screen.getByText(/^Cada fila trae la derivada parcial/)).toBeTruthy();
    expect(screen.getByText(/^bump_cost_estimate_s = 2 × insumos/)).toBeTruthy();
    expect(screen.getByText(/Diferenciación adjunta \(XAD 2\.2\.0\)/).textContent).toContain('Jacobiano de CDS: Reprecio');
    const cost = screen.getByText(/^Calculado en/).textContent ?? '';
    expect(cost).toContain('3.1 s');
    expect(cost).toContain('0.42 s');
    expect(cost).toContain('48 insumos');
    expect(cost).toContain('con la valuación en todos los hilos');
    expect(cost).toContain('40.3 s');
  });

  it('el eje de la gráfica rotula con la etiqueta del pilar sin los días (que quedan en el tooltip) y dice qué mide', () => {
    const axis = charts[charts.length - 1].option as unknown as {
      xAxis: { axisLabel: { formatter: (v: string) => string } };
      yAxis: { name: string };
    };
    expect(axis.xAxis.axisLabel.formatter('1x28 / 1M (28 d)')).toBe('1x28 / 1M');
    expect(axis.yAxis.name).toBe('CVA total, MXN por pb');
  });

  it('una gráfica de barras del CVA total por pilar, una serie por curva con total, alineada por plazo en días', () => {
    expect(screen.getByRole('img', { name: 'CVA total por pilar de TIIE-F y SOFR, en MXN por pb' })).toBeTruthy();
    const { option } = charts[charts.length - 1];
    const series = option.series ?? [];
    expect(series.map((s) => s.name)).toEqual(['TIIE-F', 'SOFR']); // MXN-USD no tiene total: no se grafica
    expect(series.every((s) => s.type === 'bar')).toBe(true);
    const cats = option.xAxis?.data ?? [];
    expect(cats).toHaveLength(19); // 20 pilares, uno de ellos (1 día) compartido
    expect(new Set(cats).size).toBe(cats.length);
    expect(cats[0]).toBe('1D (1 d)');
    const i28 = cats.indexOf('1x28 (28 d)');
    expect(i28).toBeGreaterThan(0);
    const p = FIXTURE.curves[0].pillars[1];
    expect(series[0].data[i28]).toBe(p.recalibrated?.cva); // la total, no la parcial
    expect(series[0].data[i28]).not.toBe(p.cva);
    expect(series[1].data[i28]).toBeNull();
  });
});

describe('XvaSensitivitiesPanel: casos particulares', () => {
  it('sin operaciones cubiertas avisa el motivo y no pinta tablas ni gráfica', async () => {
    const reason = 'La contraparte no tiene swaps de tasa ni cross currency swaps vivos: no hay sensibilidades del XVA';
    mocks.getXvaSensitivities.mockResolvedValue({ ...FIXTURE, curves: [], vols: [], empty_reason: reason });
    renderPanel();
    click();
    expect((await screen.findByRole('status')).textContent).toBe(reason);
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('sin la curva MXN-USD solo aparecen las otras dos', async () => {
    mocks.getXvaSensitivities.mockResolvedValue({ ...FIXTURE, curves: FIXTURE.curves.slice(0, 2) });
    renderPanel();
    click();
    await screen.findByRole('table', { name: 'Sensibilidad por curva y pilar' });
    expect(within(curvesTable()).queryByRole('rowheader', { name: 'MXN-USD' })).toBeNull();
    expect(charts[charts.length - 1].option.series?.map((s) => s.name)).toEqual(['TIIE-F', 'SOFR']);
  });

  it('muestra los avisos de la respuesta', async () => {
    mocks.getXvaSensitivities.mockResolvedValue({
      ...FIXTURE,
      warnings: [{ code: 'other', index: null, dates: [], message: 'Aviso de prueba' } as never],
    });
    renderPanel();
    click();
    expect(await screen.findByText('Aviso de prueba')).toBeTruthy();
  });
});

describe('sensitivityOption', () => {
  it('pilares con la misma etiqueta y días distintos (1M a 28 y a 30 días) no comparten categoría', () => {
    const row = (days: number) => ({ label: '1M', days, cva: 1, dva: 0, fva: 0, total: 1, recalibrated: { cva: 2, dva: 0, fva: 0, total: 2 } });
    const curve = (name: string, days: number) => ({ curve: name, pillars: [row(days)], dv01: row(days) });
    const opt = sensitivityOption([curve('A', 28), curve('B', 30)]) as { xAxis: { data: string[] } };
    expect(opt.xAxis.data).toEqual(['1M (28 d)', '1M (30 d)']);
  });

  it('solo grafica las curvas que tienen total (no MXN-USD) y con la total', () => {
    const opt = sensitivityOption(FIXTURE.curves) as { series: { name: string; data: (number | null)[] }[] };
    expect(opt.series.map((s) => s.name)).toEqual(['TIIE-F', 'SOFR']);
    expect(opt.series[1].data.filter((v) => v !== null)).toEqual(FIXTURE.curves[1].pillars.map((p) => p.recalibrated!.cva));
  });
});
