import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { INCREMENTAL_FIXTURE, XVA_FIXTURE } from './fixtures';
import {
  IncrementalChart,
  XvaProfileChart,
  alignExposure,
  incrementExtremes,
  incrementSummary,
  incrementalOption,
  profileOption,
} from './XvaProfileChart';

type TestOption = {
  series?: { name?: string; data: unknown[]; xAxisIndex?: number; areaStyle?: unknown }[];
  xAxis?: unknown;
  legend?: { data?: string[] };
};
const charts: { option: TestOption; ariaLabel?: string }[] = [];
vi.mock('../../components/EChart', () => ({
  cssColor: () => '#000',
  EChart: (props: (typeof charts)[number]) => {
    charts.push(props);
    return <div role="img" aria-label={props.ariaLabel} />;
  },
}));

const ALFA = XVA_FIXTURE.counterparties[0];

describe('profileOption', () => {
  it('traza EPE, ENE y PFE (con el percentil en la leyenda) contra la fecha', () => {
    const option = profileOption(ALFA, 0.95) as (typeof charts)[number]['option'];
    expect((option.xAxis as { data?: string[] }).data).toEqual(ALFA.profile.map((p) => p.date));
    expect(option.series?.map((s) => s.name)).toEqual(['EPE', 'ENE', 'PFE 95 %']);
    expect(option.series?.[0].data).toEqual(ALFA.profile.map((p) => p.epe_mxn));
    expect(option.series?.[1].data).toEqual(ALFA.profile.map((p) => p.ene_mxn));
    expect(option.series?.[2].data).toEqual(ALFA.profile.map((p) => p.pfe_mxn));
  });
});

const D0 = '2026-11-10';
const D1 = '2027-05-10';
const D2 = '2027-11-10';
const D3 = '2028-05-10';
const pt = (date: string, t: number, epe: number) => ({ date, t, epe });

describe('alignExposure', () => {
  it('resta después menos antes por fecha, con incrementos negativos cuando la candidata compensa', () => {
    const before = [pt(D0, 0, 0), pt(D1, 0.5, 100), pt(D2, 1, 200)];
    const after = [pt(D0, 0, 0), pt(D1, 0.5, 130), pt(D2, 1, 150)];
    const rows = alignExposure(before, after);
    expect(rows.map((r) => r.increment)).toEqual([0, 30, -50]);
    expect(rows.map((r) => [r.date, r.t, r.before, r.after])).toEqual([
      [D0, 0, 0, 0],
      [D1, 0.5, 100, 130],
      [D2, 1, 200, 150],
    ]);
  });

  it('alinea por fecha y no por índice cuando un perfil tiene fechas distintas: interpola dentro de su rango', () => {
    // El «antes» no tiene D1: su valor ahí es la interpolación en el plazo (100), no el índice 1 (que sería D2 = 200).
    const before = [pt(D0, 0, 0), pt(D2, 1, 200)];
    const after = [pt(D0, 0, 0), pt(D1, 0.5, 150), pt(D2, 1, 210)];
    const rows = alignExposure(before, after);
    expect(rows.map((r) => r.date)).toEqual([D0, D1, D2]);
    expect(rows[1].before).toBeCloseTo(100, 10);
    expect(rows[1].increment).toBeCloseTo(50, 10);
    expect(rows[2].increment).toBe(10);
  });

  it('un perfil más largo: pasado el último plazo del otro no hay exposición, y el incremento es todo el EPE', () => {
    const before = [pt(D0, 0, 0), pt(D1, 0.5, 100)];
    const after = [pt(D0, 0, 0), pt(D1, 0.5, 90), pt(D2, 1, 70), pt(D3, 1.5, 40)];
    const rows = alignExposure(before, after);
    expect(rows.map((r) => r.increment)).toEqual([0, -10, 70, 40]);
    expect(rows[3].before).toBe(0);
    // y al revés: la candidata vence antes y su perfil «después» es 0 en la cola
    const back = alignExposure(after, before);
    expect(back.map((r) => r.increment)).toEqual([0, 10, -70, -40]);
  });

  it('antes del primer plazo de un perfil no hay valor: se omite en vez de inventarlo', () => {
    const before = [pt(D1, 0.5, 100), pt(D2, 1, 200)];
    const after = [pt(D0, 0, 5), pt(D1, 0.5, 120), pt(D2, 1, 180)];
    const rows = alignExposure(before, after);
    expect(rows[0]).toMatchObject({ date: D0, before: null, after: 5, increment: null });
    expect(rows.slice(1).map((r) => r.increment)).toEqual([20, -20]);
  });

  it('ordena por fecha aunque lleguen desordenados y no muta las entradas', () => {
    const before = [pt(D2, 1, 200), pt(D0, 0, 0)];
    const after = [pt(D2, 1, 100), pt(D0, 0, 0)];
    const copy = JSON.stringify([before, after]);
    expect(alignExposure(before, after).map((r) => r.date)).toEqual([D0, D2]);
    expect(JSON.stringify([before, after])).toBe(copy);
  });

  it('perfiles vacíos dan una lista vacía', () => {
    expect(alignExposure([], [])).toEqual([]);
  });
});

describe('incrementExtremes e incrementSummary', () => {
  const rows = alignExposure(
    [pt(D0, 0, 0), pt(D1, 0.5, 100), pt(D2, 1, 200), pt(D3, 1.5, 100)],
    [pt(D0, 0, 0), pt(D1, 0.5, 130), pt(D2, 1, 150), pt(D3, 1.5, 180)],
  );

  it('halla el máximo y el mínimo del incremento con su plazo y su fecha', () => {
    const ex = incrementExtremes(rows)!;
    expect(ex.max).toMatchObject({ date: D3, t: 1.5, increment: 80 });
    expect(ex.min).toMatchObject({ date: D2, t: 1, increment: -50 });
  });

  it('ignora los plazos sin incremento y devuelve null si no hay ninguno', () => {
    const sparse = alignExposure([pt(D1, 0.5, 100)], [pt(D0, 0, 5), pt(D1, 0.5, 120)]);
    expect(incrementExtremes(sparse)!.max.increment).toBe(20);
    expect(incrementExtremes([])).toBeNull();
    expect(incrementSummary([])).toBeNull();
  });

  it('redacta el máximo y el mínimo en español, con MXN, años y fecha', () => {
    expect(incrementSummary(rows)).toBe(
      'Incremento de exposición: máximo MXN 80.00 a 1.50 años (2028-05-10); mínimo MXN -50.00 a 1.00 años (2027-11-10).',
    );
  });
});

describe('incrementalOption', () => {
  const profile = [
    { date: D0, t: 0, epe_before_mxn: 0, ene_before_mxn: 7, epe_after_mxn: 0, ene_after_mxn: 7 },
    { date: D1, t: 0.5, epe_before_mxn: 100, ene_before_mxn: 7, epe_after_mxn: 130, ene_after_mxn: 7 },
    { date: D2, t: 1, epe_before_mxn: 200, ene_before_mxn: 7, epe_after_mxn: 150, ene_after_mxn: 7 },
  ];
  const opt = () => incrementalOption(profile) as TestOption & { yAxis: unknown[]; grid: unknown[] };

  it('rotula en español: EPE antes, EPE después e incremento de exposición, sin ENE', () => {
    const option = opt();
    const names = option.series!.map((s) => s.name);
    expect(names.slice(0, 3)).toEqual(['Exposición esperada antes', 'Exposición esperada después', 'Incremento de exposición']);
    expect(option.legend!.data).toEqual(names.slice(0, 3));
    expect(names.join(' ')).not.toMatch(/ENE/);
  });

  it('traza antes y después en un panel y el incremento (con área) en otro, contra el plazo en años', () => {
    const option = opt();
    const [before, after, inc] = option.series!;
    expect(before.data).toEqual([[0, 0], [0.5, 100], [1, 200]]);
    expect(after.data).toEqual([[0, 0], [0.5, 130], [1, 150]]);
    expect(inc.data).toEqual([[0, 0], [0.5, 30], [1, -50]]);
    expect(inc.areaStyle).toBeTruthy();
    expect(before.xAxisIndex).toBe(0);
    expect(inc.xAxisIndex).toBe(1);
    expect(option.grid).toHaveLength(2);
    const axes = option.xAxis as { type?: string; name?: string }[];
    expect(axes.map((a) => a.type)).toEqual(['value', 'value']);
    expect(axes[1].name).toBe('Plazo (años)');
  });

  it('con un perfil vacío no truena y no traza nada', () => {
    const option = incrementalOption([]) as TestOption;
    expect(option.series!.slice(0, 3).map((x) => x.data)).toEqual([[], [], []]);
  });
});

describe('componentes de gráfica', () => {
  it('XvaProfileChart pasa la opción de la contraparte elegida', () => {
    charts.length = 0;
    render(<XvaProfileChart cp={ALFA} pfeQuantile={0.95} />);
    expect(screen.getByRole('img', { name: 'Perfil de exposición' })).toBeTruthy();
    expect(charts[charts.length - 1].option.series?.[0].data).toEqual(ALFA.profile.map((p) => p.epe_mxn));
  });

  it('IncrementalChart pone título, gráfica y la línea con el máximo y el mínimo del incremento', () => {
    render(<IncrementalChart profile={INCREMENTAL_FIXTURE.profile} />);
    expect(screen.getByRole('heading', { name: 'Exposición esperada antes y después de la operación' })).toBeTruthy();
    expect(
      screen.getByRole('img', { name: 'Exposición esperada antes y después de la operación, e incremento de exposición' }),
    ).toBeTruthy();
    // fixture: incrementos 0, 20 000, 50 000 y 30 000
    expect(screen.getByText(/máximo MXN 50,000\.00 a 1\.00 años \(2027-11-10\); mínimo MXN 0\.00 a 0\.00 años \(2026-11-10\)/)).toBeTruthy();
  });

  it('IncrementalChart sin perfil no inventa la línea de resumen', () => {
    render(<IncrementalChart profile={[]} />);
    expect(screen.queryByText(/Incremento de exposición:/)).toBeNull();
  });
});
