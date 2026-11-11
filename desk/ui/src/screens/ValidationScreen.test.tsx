import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { ValidationReport } from '../api/types';
import ValidationScreen from './ValidationScreen';
import { VALIDATION_REPORT } from './validationFixture';

const mocks = vi.hoisted(() => ({
  getValidationReport: vi.fn()
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, getValidationReport: mocks.getValidationReport };
});

function mount(report: ValidationReport = VALIDATION_REPORT) {
  mocks.getValidationReport.mockResolvedValue(report);
  return render(<ValidationScreen />);
}

/** Filas del cuerpo de la tabla con ese nombre accesible. */
function bodyRows(name: string): HTMLElement[] {
  const table = screen.getByRole('table', { name });
  return within(table).getAllByRole('row').slice(1);
}

describe('ValidationScreen', () => {
  beforeEach(() => {
    mocks.getValidationReport.mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('muestra la procedencia y las siete filas del resumen por producto', async () => {
    mount();
    expect(await screen.findByRole('heading', { name: 'Validación independiente', level: 1 })).toBeTruthy();
    expect(screen.getByText(/QuantLib 1\.44/).textContent).toContain('Generado el 2026-11-11 20:02 UTC · QuantLib 1.44 (Python 3.12.16, entorno quantsuite-oracle) · snapshot MX-DEMO al 2026-11-10 · commit ce51edf');
    expect(screen.getByText(/dentro de tolerancia ·/).textContent).toContain('10 casos · 9 dentro de tolerancia · 1 con diferencia explicada · 0 fuera de tolerancia');
    const rows = bodyRows('Resumen por producto');
    expect(rows).toHaveLength(7);
    const bond = rows.find((r) => within(r).queryByText('Bono de tasa fija'))!;
    expect(within(bond).getByText('3.05e-6')).toBeTruthy();
    expect(within(bond).getAllByText('1.00e-6').length).toBeGreaterThan(0);
  });

  it('muestra las dos curvas como idénticas con sus tolerancias', async () => {
    mount();
    await screen.findByRole('table', { name: 'Curvas' });
    const rows = bodyRows('Curvas');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText('TIIE-F')).toBeTruthy();
    expect(within(rows[0]).getByText('Idénticas')).toBeTruthy();
    expect(within(rows[0]).getByText('pilares 1.00e-12 · intermedias 1.00e-8')).toBeTruthy();
    expect(within(rows[1]).getByText('1.10e-16')).toBeTruthy();
    expect(within(rows[1]).getByText('0')).toBeTruthy();
  });

  it('filtrar por producto deja solo sus casos y actualiza "Mostrando"', async () => {
    mount();
    await screen.findByRole('table', { name: 'Casos' });
    expect(bodyRows('Casos')).toHaveLength(10);
    expect(screen.getByText('Mostrando 10 de 10 casos')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Producto'), { target: { value: 'swaption' } });
    const rows = bodyRows('Casos');
    expect(rows).toHaveLength(2);
    rows.forEach((r) => expect(within(r).getByText('Swaption (Hull-White)')).toBeTruthy());
    expect(screen.getByText('Mostrando 2 de 10 casos')).toBeTruthy();
  });

  it('filtrar por "Diferencia explicada" deja solo el caso explicado', async () => {
    mount();
    await screen.findByRole('table', { name: 'Casos' });
    fireEvent.change(screen.getByLabelText('Veredicto'), { target: { value: 'explained' } });
    const rows = bodyRows('Casos');
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByText('bond-08')).toBeTruthy();
    expect(within(rows[0]).getByText('Diferencia explicada')).toBeTruthy();
    expect(screen.getByText('Mostrando 1 de 10 casos')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Veredicto'), { target: { value: 'fail' } });
    expect(bodyRows('Casos')).toHaveLength(0);
    expect(screen.getByText('Mostrando 0 de 10 casos')).toBeTruthy();
  });

  it('marca el caso del portafolio y formatea PV y diferencias', async () => {
    mount();
    await screen.findByRole('table', { name: 'Casos' });
    const rows = bodyRows('Casos');
    const irs01 = rows.find((r) => within(r).queryByText('irs-01'))!;
    expect(within(irs01).getByText('Portafolio de ejemplo')).toBeTruthy();
    expect(within(irs01).getAllByText('-8,423,117.44')).toHaveLength(2);
    expect(within(irs01).getByText('4.20e-12')).toBeTruthy();
    expect(within(irs01).getByText('Dentro de tolerancia')).toBeTruthy();
    const irs04 = rows.find((r) => within(r).queryByText('irs-04'))!;
    expect(within(irs04).queryByText('Portafolio de ejemplo')).toBeNull();
  });

  it('un caso sin referencia muestra "—" y el error como title', async () => {
    const broken: ValidationReport = {
      ...VALIDATION_REPORT,
      cases: [
        {
          ...VALIDATION_REPORT.cases[0],
          pv_ref: null,
          abs_diff: null,
          rel_diff: null,
          verdict: 'fail',
          error: 'QuantLib no pudo valuar el caso'
        }
      ]
    };
    mount(broken);
    await screen.findByRole('table', { name: 'Casos' });
    const [row] = bodyRows('Casos');
    expect(within(row).getAllByText('—')).toHaveLength(3);
    expect(within(row).getByText('Fuera de tolerancia').getAttribute('title')).toBe('QuantLib no pudo valuar el caso');
  });

  it('la diferencia conocida muestra su tipo, su causa y sus magnitudes', async () => {
    mount();
    await screen.findByText('Diferencias conocidas');
    const article = screen.getByText(/^bond-08 ·/).closest('article')!;
    expect(within(article).getByText('Fechas de pago fraccionarias')).toBeTruthy();
    expect(within(article).getByText(/QuantLib solo admite fechas enteras/)).toBeTruthy();
    expect(within(article).getByText('Tipo').nextElementSibling?.textContent).toContain('Convención');
    expect(within(article).getByText(/esperada 3\.10e-6/).textContent).toContain('esperada 3.10e-6 · observada 3.05e-6 · tolerancia 1.00e-6');
  });

  it('sin diferencias conocidas dice que todo está dentro de su tolerancia', async () => {
    mount({ ...VALIDATION_REPORT, known_differences: [] });
    expect(await screen.findByText('Ninguna: todos los casos están dentro de su tolerancia.')).toBeTruthy();
  });

  it('no muestra avisos con commit_matches true y desk_dirty false', async () => {
    mount();
    await screen.findByRole('table', { name: 'Casos' });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('avisa con ambos commits a 7 caracteres si el código cambió', async () => {
    mount({
      ...VALIDATION_REPORT,
      commit_matches: false,
      current_commit: '91b622a5c0d4e7f9a3b268ce51edf0c1a4b7d93e'
    });
    const warning = await screen.findByRole('status');
    expect(warning.className).toBe('vld-warning');
    expect(warning.textContent).toContain('El reporte se generó con el commit ce51edf y el código de valuación actual está en 91b622a: regenera el reporte (ver «Cómo reproducir»).');
  });

  it('avisa si no se pudo determinar el commit actual', async () => {
    mount({ ...VALIDATION_REPORT, commit_matches: null, current_commit: null });
    expect((await screen.findByRole('status')).textContent).toContain('No se pudo determinar el commit actual del código de valuación.');
  });

  it('avisa si el reporte se generó con cambios sin commit', async () => {
    mount({ ...VALIDATION_REPORT, desk_dirty: true });
    expect((await screen.findByRole('status')).textContent).toContain('El reporte se generó con cambios sin commit en el código de valuación.');
  });

  it('un 404 dice que aún no hay reporte', async () => {
    mocks.getValidationReport.mockRejectedValue(
      new ApiError(404, 'Aún no hay reporte de validación: genera uno con desk/validation/make_report.sh')
    );
    render(<ValidationScreen />);
    expect((await screen.findByRole('status')).textContent).toContain('Aún no hay reporte de validación. Genera uno con desk/validation/make_report.sh.');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('otro error se muestra en una banda con su mensaje', async () => {
    mocks.getValidationReport.mockRejectedValue(new ApiError(500, 'Error interno'));
    render(<ValidationScreen />);
    expect((await screen.findByRole('alert')).textContent).toContain('Error interno');
  });

  it('un fallo de red se muestra como falta de conexión con el backend', async () => {
    mocks.getValidationReport.mockRejectedValue(new TypeError('Failed to fetch'));
    render(<ValidationScreen />);
    expect((await screen.findByRole('alert')).textContent).toContain('No se pudo conectar con el backend');
  });

  it('"Cómo reproducir" muestra el comando, los pasos y los dos Python', async () => {
    mount();
    const heading = await screen.findByRole('heading', { name: 'Cómo reproducir' });
    const card = heading.closest('.vld-card') as HTMLElement;
    const pre = card.querySelector('pre')!;
    expect(pre.textContent).toContain('desk/validation/make_report.sh');
    expect(pre.textContent).toContain('1. python -m desk.validation.export_cases');
    expect(pre.textContent).toContain('3. python -m desk.validation.compare');
    expect(within(card).getByText(/\/home\/claudio\/anaconda3\/bin\/python/)).toBeTruthy();
    expect(within(card).getByText(/quantsuite-oracle\/bin\/python/)).toBeTruthy();
  });
});
