import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { CreditCurve } from '../../api/xvaTypes';
import { CREDIT_CURVES_FIXTURE } from './fixtures';
import { CreditCurvesPanel, survivalOption } from './CreditCurvesPanel';

const mocks = vi.hoisted(() => ({ getCreditCurves: vi.fn(), putCreditCurve: vi.fn() }));
vi.mock('../../api/xvaClient', () => ({ getCreditCurves: mocks.getCreditCurves, putCreditCurve: mocks.putCreditCurve }));

const charts: { option: { series?: { name?: string; data: unknown[] }[] }; ariaLabel?: string }[] = [];
vi.mock('../../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: (typeof charts)[number]) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

const [OWN, ALFA, BETA] = CREDIT_CURVES_FIXTURE.curves;
const NO_CURVE: CreditCurve = {
  entity: 'Banco Zeta',
  label: 'Banco Zeta',
  kind: 'counterparty',
  id: null,
  as_of: null,
  recovery: null,
  quotes: [],
  history: [],
  error: null,
};

const input = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const pick = (entity: string) => fireEvent.change(screen.getByLabelText('Entidad'), { target: { value: entity } });

async function renderPanel(onSaved = vi.fn()) {
  render(<CreditCurvesPanel snapshotId="MX-DEMO" onSaved={onSaved} />);
  await screen.findByLabelText('Entidad');
  return onSaved;
}

beforeEach(() => {
  charts.length = 0;
  mocks.getCreditCurves.mockResolvedValue({ ...CREDIT_CURVES_FIXTURE, curves: [...CREDIT_CURVES_FIXTURE.curves, NO_CURVE] });
  mocks.putCreditCurve.mockImplementation(async (entity: string) => ({ ...OWN, entity }));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('CreditCurvesPanel: lectura', () => {
  it('pide las curvas del snapshot y las marca como sintéticas', async () => {
    await renderPanel();
    expect(mocks.getCreditCurves).toHaveBeenCalledWith('MX-DEMO');
    expect(screen.getByText('Sintética')).toBeTruthy();
    expect(screen.getByText('Sintética (inventada para demostración)')).toBeTruthy();
    const options = within(screen.getByLabelText('Entidad')).getAllByRole('option').map((o) => o.textContent);
    expect(options).toEqual(['Propia (el desk)', 'Banco Alfa (sintético)', 'Banco Beta (sintético)', 'Banco Gamma (sintético)', 'Banco Zeta']);
  });

  it('la propia abre primero, con sus cotizaciones en pb y la recuperación en %', async () => {
    await renderPanel();
    expect(input('Recuperación (%)').value).toBe('40');
    OWN.quotes.forEach((q, i) => {
      expect(input(`Plazo ${i + 1} (años)`).value).toBe(String(q.tenor_years));
    });
    expect(input('Spread 1 (pb)').value).toBe('70');
    expect(input('Spread 6 (pb)').value).toBe('125');
  });

  it('muestra la supervivencia, la PD acumulada y la PD del año para cada año', async () => {
    await renderPanel();
    const table = screen.getByRole('table', { name: 'Probabilidad de incumplimiento por año' });
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Año',
      'Supervivencia',
      'PD acumulada',
      'PD del año',
    ]);
    const rows = within(table).getAllByRole('row');
    expect(rows).toHaveLength(1 + 10);
    const g = OWN.grid![0];
    const cells = within(rows[1]).getAllByRole('cell').map((c) => c.textContent);
    expect(cells[0]).toBe('1');
    expect(cells[1]).toBe(`${(g.survival * 100).toFixed(2)} %`);
    expect(cells[2]).toBe(`${(g.cumulative_pd * 100).toFixed(2)} %`);
    expect(cells[3]).toBe(`${(g.marginal_pd * 100).toFixed(2)} %`);
  });

  it('grafica la supervivencia desde 100 % en el año 0', async () => {
    await renderPanel();
    const chart = charts[charts.length - 1];
    expect(chart.ariaLabel).toBe('Curva de supervivencia');
    const data = chart.option.series![0].data;
    expect(data).toHaveLength(11);
    expect(data[0]).toBe(1);
    expect(data[1]).toBe(OWN.grid![0].survival);
  });

  it('cambiar de entidad cambia cotizaciones, tabla y gráfica', async () => {
    await renderPanel();
    pick('Banco Alfa (sintético)');
    expect(input('Spread 1 (pb)').value).toBe('60');
    expect(charts[charts.length - 1].option.series![0].data[1]).toBe(ALFA.grid![0].survival);
  });

  it('una curva cuyo ajuste falla muestra el error y deja corregir las cotizaciones', async () => {
    await renderPanel();
    pick('Banco Beta (sintético)');
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain(BETA.error);
    expect(screen.queryByRole('table', { name: 'Probabilidad de incumplimiento por año' })).toBeNull();
    expect(input('Spread 1 (pb)').value).toBe('150');
  });

  it('si no carga las curvas lo dice', async () => {
    mocks.getCreditCurves.mockRejectedValue(new ApiError(404, 'Snapshot inexistente: X', 'snapshot'));
    render(<CreditCurvesPanel snapshotId="X" onSaved={() => {}} />);
    expect((await screen.findByRole('alert')).textContent).toBe('Snapshot inexistente: X');
  });
});

describe('CreditCurvesPanel: edición', () => {
  it('guarda con los spreads en decimal y la recuperación en decimal, y avisa para recalcular', async () => {
    const onSaved = await renderPanel();
    fireEvent.change(input('Spread 1 (pb)'), { target: { value: '65' } });
    fireEvent.change(input('Recuperación (%)'), { target: { value: '35' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(mocks.putCreditCurve).toHaveBeenCalledWith('propia', {
      recovery: 0.35,
      quotes: OWN.quotes.map((q, i) => ({ tenor_years: q.tenor_years, spread: i === 0 ? 0.0065 : q.spread })),
      snapshot: 'MX-DEMO',
    });
    // recarga lo vigente
    await waitFor(() => expect(mocks.getCreditCurves).toHaveBeenCalledTimes(2));
  });

  it('un 400 de cotizaciones se muestra junto a la tabla de cotizaciones', async () => {
    mocks.putCreditCurve.mockRejectedValue(
      new ApiError(400, 'Las cotizaciones implican una intensidad de incumplimiento negativa en el tramo de 2 años', 'quotes'),
    );
    const onSaved = await renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('intensidad de incumplimiento negativa');
    expect(alert.id).toBe('credit-quotes-error');
    expect(onSaved).not.toHaveBeenCalled();
  });

  it('un 400 de recuperación se muestra junto al campo', async () => {
    mocks.putCreditCurve.mockRejectedValue(new ApiError(400, 'recovery debe estar en [0, 1)', 'recovery'));
    await renderPanel();
    fireEvent.change(input('Recuperación (%)'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('recovery debe estar en [0, 1)');
    expect(input('Recuperación (%)').getAttribute('aria-describedby')).toBe(alert.id);
  });

  it('una celda vacía no llega al servidor', async () => {
    await renderPanel();
    fireEvent.change(input('Spread 2 (pb)'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Ingresa un número válido en cada plazo y spread');
    expect(mocks.putCreditCurve).not.toHaveBeenCalled();
  });

  it('permite quitar y agregar cotizaciones', async () => {
    await renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Quitar cotización 6' }));
    expect(screen.queryByLabelText('Plazo 6 (años)')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Agregar cotización' }));
    expect(input('Plazo 6 (años)').value).toBe('');
    fireEvent.change(input('Plazo 6 (años)'), { target: { value: '15' } });
    fireEvent.change(input('Spread 6 (pb)'), { target: { value: '130' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));
    await waitFor(() => expect(mocks.putCreditCurve).toHaveBeenCalled());
    const body = mocks.putCreditCurve.mock.calls[0][1];
    expect(body.quotes).toHaveLength(6);
    expect(body.quotes[5]).toEqual({ tenor_years: 15, spread: 0.013 });
  });

  it('una contraparte sin curva parte vacía con recuperación de 40 %', async () => {
    await renderPanel();
    pick('Banco Zeta');
    expect(input('Recuperación (%)').value).toBe('40');
    expect(screen.queryByLabelText('Plazo 1 (años)')).toBeNull();
    expect(screen.getByText('Sin curva: el XVA usa el respaldo plano de esta contraparte.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Agregar cotización' }));
    fireEvent.change(input('Plazo 1 (años)'), { target: { value: '1' } });
    fireEvent.change(input('Spread 1 (pb)'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar curva' }));
    await waitFor(() =>
      expect(mocks.putCreditCurve).toHaveBeenCalledWith('Banco Zeta', {
        recovery: 0.4,
        quotes: [{ tenor_years: 1, spread: 0.01 }],
        snapshot: 'MX-DEMO',
      }),
    );
  });
});

describe('CreditCurvesPanel: texto solo para lectores de pantalla', () => {
  it('la cabecera «Quitar» sigue en el DOM, dentro del contenedor de la tabla', async () => {
    await renderPanel();
    const sr = document.querySelector('.xva-sr');
    expect(sr?.textContent).toBe('Quitar');
    expect(sr?.closest('.xva-scroll')).not.toBeNull();
  });

  it('ese contenedor es el ancestro posicionado de .xva-sr (verificación estática)', async () => {
    // Un `position: absolute` sin ancestro posicionado cuelga del bloque inicial: ni el `overflow` del
    // contenedor de la tabla lo recorta y agranda el documento (10 px de desborde en `/xva` a 1280 px).
    // jsdom no calcula la maquetación; el desborde real se midió en navegador. `fs` se importa con
    // especificador no literal (el proyecto no trae @types/node).
    const { readFileSync } = (await import(/* @vite-ignore */ 'node:fs' as string)) as {
      readFileSync(path: string, encoding: string): string;
    };
    const css = readFileSync('src/screens/XvaScreen.css', 'utf8');
    const rule = (selector: string) => new RegExp(`(?:^|\\n)${selector.replace('.', '\\.')}\\s*\\{([^}]*)\\}`).exec(css)?.[1] ?? '';
    expect(rule('.xva-sr')).toMatch(/position:\s*absolute/);
    expect(rule('.xva-scroll')).toMatch(/position:\s*relative/);
  });
});

describe('survivalOption', () => {
  it('antepone el año 0 con supervivencia 1', () => {
    const option = survivalOption(OWN) as (typeof charts)[number]['option'];
    expect(option.series![0].data).toEqual([1, ...OWN.grid!.map((g) => g.survival)]);
  });
});
