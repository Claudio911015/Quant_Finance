import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { INCREMENTAL_FIXTURE, XVA_FIXTURE } from './fixtures';
import { IncrementalChart, XvaProfileChart, incrementalOption, profileOption } from './XvaProfileChart';

const charts: { option: { series?: { name?: string; data: unknown[] }[]; xAxis?: { data?: string[] } }; ariaLabel?: string }[] = [];
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
    expect(option.xAxis?.data).toEqual(ALFA.profile.map((p) => p.date));
    expect(option.series?.map((s) => s.name)).toEqual(['EPE', 'ENE', 'PFE 95 %']);
    expect(option.series?.[0].data).toEqual(ALFA.profile.map((p) => p.epe_mxn));
    expect(option.series?.[1].data).toEqual(ALFA.profile.map((p) => p.ene_mxn));
    expect(option.series?.[2].data).toEqual(ALFA.profile.map((p) => p.pfe_mxn));
  });
});

describe('incrementalOption', () => {
  it('superpone EPE y ENE antes y después de la operación', () => {
    const option = incrementalOption(INCREMENTAL_FIXTURE.profile) as (typeof charts)[number]['option'];
    expect(option.series?.map((s) => s.name)).toEqual(['EPE antes', 'EPE después', 'ENE antes', 'ENE después']);
    expect(option.series?.[1].data).toEqual(INCREMENTAL_FIXTURE.profile.map((p) => p.epe_after_mxn));
    expect(option.series?.[2].data).toEqual(INCREMENTAL_FIXTURE.profile.map((p) => p.ene_before_mxn));
  });
});

describe('componentes de gráfica', () => {
  it('XvaProfileChart pasa la opción de la contraparte elegida', () => {
    charts.length = 0;
    render(<XvaProfileChart cp={ALFA} pfeQuantile={0.95} />);
    expect(screen.getByRole('img', { name: 'Perfil de exposición' })).toBeTruthy();
    expect(charts[charts.length - 1].option.series?.[0].data).toEqual(ALFA.profile.map((p) => p.epe_mxn));
  });

  it('IncrementalChart rotula la gráfica de antes y después', () => {
    render(<IncrementalChart profile={INCREMENTAL_FIXTURE.profile} />);
    expect(screen.getByRole('img', { name: 'EPE y ENE antes y después de la operación' })).toBeTruthy();
  });
});
