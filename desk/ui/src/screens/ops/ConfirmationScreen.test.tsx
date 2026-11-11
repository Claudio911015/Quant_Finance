import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { Confirmation } from '../../api/opsTypes';
import ConfirmationScreen from './ConfirmationScreen';

const mocks = vi.hoisted(() => ({
  getConfirmation: vi.fn(),
  getSettings: vi.fn(),
  putSettings: vi.fn(),
}));

vi.mock('../../api/opsClient', () => mocks);

const NOTICES = [
  'Documento informativo; no sustituye la confirmación ISDA ni el contrato marco firmado por las partes.',
  'Generado por QF Desk con los términos registrados; los montos variables dependen de fijaciones futuras.',
];

const COMPANY = 'Tesorería Ejemplo, S.A. de C.V.';

const DOC: Confirmation = {
  trade_id: 1,
  product: 'irs',
  product_label: 'Swap de tasa de interés (OIS)',
  generated_at: '2026-11-11T18:00:00+00:00',
  parties: {
    company: COMPANY,
    counterparty: 'Banco Alfa (sintético)',
    company_role: 'Paga tasa fija',
    counterparty_role: 'Paga tasa variable',
  },
  bank_ref: 'BA-2026-0042',
  dates: { trade_date: '2026-11-10', start_date: '2026-11-10', maturity_date: '2028-10-31' },
  terms: [
    { key: 'notional', label: 'Nocional', value: 500000000, format: 'amount', currency: 'MXN' },
    { key: 'fixed_rate', label: 'Tasa fija', value: 0.068, format: 'rate', currency: null },
    { key: 'periods', label: 'Periodos', value: 26, format: 'number', currency: null },
    { key: 'strike', label: 'Strike', value: 19.5, format: 'number', currency: null },
  ],
  conventions: [
    { key: 'index', label: 'Índice variable', value: 'TIIE de Fondeo (TIIE-F)', format: 'text', currency: null },
    { key: 'day_count', label: 'Base de días', value: 'ACT/360', format: 'text', currency: null },
    { key: 'first_fixing', label: 'Primera fijación', value: '2026-11-10', format: 'date', currency: null },
  ],
  schedule: [
    { date: '2026-12-08', description: 'Cupón 1: pierna fija contra pierna variable', amount: -264444.44, currency: 'MXN' },
    { date: '2027-01-05', description: 'Liquidación por diferencias: nocional × (FIX − strike)', amount: null, currency: 'MXN' },
  ],
  events_note: null,
  notices: NOTICES,
};

function renderAt(path = '/portafolio/1/confirmacion') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/portafolio/:id/confirmacion" element={<ConfirmationScreen />} />
        <Route path="/portafolio/:id" element={<div data-testid="trade-page" />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mocks.getConfirmation.mockResolvedValue(DOC);
  mocks.getSettings.mockResolvedValue({ company_name: COMPANY });
  mocks.putSettings.mockImplementation(async (b: { company_name: string }) => b);
});

afterEach(() => {
  vi.restoreAllMocks();
  mocks.getConfirmation.mockReset();
  mocks.getSettings.mockReset();
  mocks.putSettings.mockReset();
});

function section(title: string): HTMLElement {
  const h = screen.getByRole('heading', { name: title });
  return h.closest('section') as HTMLElement;
}

describe('ConfirmationScreen', () => {
  it('pinta el encabezado y las seis secciones con los datos de la confirmación', async () => {
    renderAt();
    expect(await screen.findByRole('heading', { name: 'Confirmación de operación', level: 1 })).toBeTruthy();
    expect(mocks.getConfirmation).toHaveBeenCalledWith(1);
    expect(
      screen.getByText('Swap de tasa de interés (OIS) · Operación 1 · Generada 2026-11-11 18:00 UTC'),
    ).toBeTruthy();

    const titles = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(titles).toEqual([
      'Partes',
      'Fechas',
      'Términos económicos',
      'Convenciones',
      'Calendario de pagos previsto',
      'Avisos',
    ]);

    const partes = within(section('Partes'));
    expect(partes.getByText(`${COMPANY} (Paga tasa fija)`)).toBeTruthy();
    expect(partes.getByText('Banco Alfa (sintético) (Paga tasa variable)')).toBeTruthy();
    expect(partes.getByText('BA-2026-0042')).toBeTruthy();

    const fechas = within(section('Fechas'));
    expect(fechas.getByText('Fecha de pacto').nextElementSibling?.textContent).toBe('2026-11-10');
    expect(fechas.getByText('Fecha de vencimiento').nextElementSibling?.textContent).toBe('2028-10-31');

    const terminos = within(section('Términos económicos'));
    expect(terminos.getByText('Nocional').nextElementSibling?.textContent).toBe('MXN 500,000,000.00');
    expect(terminos.getByText('Tasa fija').nextElementSibling?.textContent).toBe('6.8000 %');
    expect(terminos.getByText('Periodos').nextElementSibling?.textContent).toBe('26');
    expect(terminos.getByText('Strike').nextElementSibling?.textContent).toBe('19.50');

    const conv = within(section('Convenciones'));
    expect(conv.getByText('Índice variable').nextElementSibling?.textContent).toBe('TIIE de Fondeo (TIIE-F)');
    expect(conv.getByText('Primera fijación').nextElementSibling?.textContent).toBe('2026-11-10');

    const avisos = within(section('Avisos'));
    for (const n of NOTICES) expect(avisos.getByText(n)).toBeTruthy();
  });

  it('el calendario muestra "Por determinar" cuando el monto es null', async () => {
    renderAt();
    const cal = within(await screen.findByRole('heading', { name: 'Calendario de pagos previsto' }).then(
      (h) => h.closest('section') as HTMLElement,
    ));
    const rows = cal.getAllByRole('row');
    // encabezado + dos renglones
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText('Cupón 1: pierna fija contra pierna variable')).toBeTruthy();
    expect(within(rows[1]).getByText('MXN -264,444.44')).toBeTruthy();
    expect(within(rows[2]).getByText('Por determinar')).toBeTruthy();
  });

  it('muestra la nota de eventos solo si existe y "—" si no hay referencia del banco', async () => {
    mocks.getConfirmation.mockResolvedValue({
      ...DOC,
      bank_ref: null,
      events_note:
        'La operación tiene eventos posteriores al pacto (amortización): esta confirmación muestra los términos pactados.',
    });
    renderAt();
    expect(
      await screen.findByText(/La operación tiene eventos posteriores al pacto \(amortización\)/),
    ).toBeTruthy();
    expect(within(section('Partes')).getByText('Referencia del banco').nextElementSibling?.textContent).toBe('—');
  });

  it('sin nota de eventos no pinta ninguna', async () => {
    renderAt();
    await screen.findByRole('heading', { name: 'Avisos' });
    expect(screen.queryByText(/eventos posteriores al pacto/)).toBeNull();
  });

  it('guardar el nombre llama putSettings({company_name}) y vuelve a pedir la confirmación', async () => {
    renderAt();
    const input = (await screen.findByLabelText('Nombre de la empresa')) as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe(COMPANY));
    expect(mocks.getConfirmation).toHaveBeenCalledTimes(1);

    mocks.getConfirmation.mockResolvedValue({
      ...DOC,
      parties: { ...DOC.parties, company: 'Nueva Empresa, S.A.' },
    });
    fireEvent.change(input, { target: { value: '  Nueva Empresa, S.A.  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(mocks.putSettings).toHaveBeenCalledWith({ company_name: 'Nueva Empresa, S.A.' }));
    await waitFor(() => expect(mocks.getConfirmation).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Nueva Empresa, S.A. (Paga tasa fija)')).toBeTruthy();
  });

  it('un error al guardar el nombre se muestra y no recarga la confirmación', async () => {
    mocks.putSettings.mockRejectedValue(new ApiError(400, 'company_name demasiado largo', 'company_name'));
    renderAt();
    const input = (await screen.findByLabelText('Nombre de la empresa')) as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe(COMPANY));
    fireEvent.change(input, { target: { value: 'X' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect((await screen.findByRole('alert')).textContent).toBe('company_name demasiado largo');
    expect(mocks.getConfirmation).toHaveBeenCalledTimes(1);
  });

  it('si no se pueden leer los ajustes, el editor parte del nombre de la confirmación', async () => {
    mocks.getSettings.mockRejectedValue(new Error('sin red'));
    renderAt();
    const input = (await screen.findByLabelText('Nombre de la empresa')) as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe(COMPANY));
  });

  it('Imprimir llama a window.print y Volver lleva a la operación', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    renderAt();
    await screen.findByRole('heading', { name: 'Avisos' });
    fireEvent.click(screen.getByRole('button', { name: 'Imprimir' }));
    expect(print).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('link', { name: '← Volver a la operación' }));
    expect(screen.getByTestId('trade-page')).toBeTruthy();
  });

  it('la barra de acciones es no imprimible', async () => {
    renderAt();
    await screen.findByRole('heading', { name: 'Avisos' });
    const bar = screen.getByRole('button', { name: 'Imprimir' }).closest('.ops-no-print');
    expect(bar).toBeTruthy();
    expect(bar?.contains(screen.getByLabelText('Nombre de la empresa'))).toBe(true);
  });

  it('un error del backend se muestra como aviso y no pinta secciones', async () => {
    mocks.getConfirmation.mockRejectedValue(new ApiError(404, 'Operación 99 no encontrada', 'id'));
    renderAt('/portafolio/99/confirmacion');
    expect((await screen.findByRole('alert')).textContent).toBe('Operación 99 no encontrada');
    expect(screen.queryByRole('heading', { name: 'Partes' })).toBeNull();
  });

  it('un id inválido no consulta al backend', () => {
    renderAt('/portafolio/abc/confirmacion');
    expect(screen.getByRole('alert').textContent).toBe('Operación inválida');
    expect(mocks.getConfirmation).not.toHaveBeenCalled();
  });

  it('el CSS imprime sin barra lateral, barra superior ni acciones (verificación estática)', async () => {
    // El proyecto no trae @types/node (ni se agregan paquetes): `fs` se importa con especificador no
    // literal para que `tsc -b` no lo tipe. Vitest corre con la raíz en `desk/ui` (como `npm test`).
    const { readFileSync } = (await import(/* @vite-ignore */ 'node:fs' as string)) as {
      readFileSync(path: string, encoding: string): string;
    };
    const css = readFileSync('src/screens/ops/ConfirmationScreen.css', 'utf8');
    const idx = css.indexOf('@media print');
    expect(idx).toBeGreaterThanOrEqual(0);
    const printCss = css.slice(idx);
    expect(printCss).toContain('.shell__sidebar');
    expect(printCss).toContain('.shell__topbar');
    expect(printCss).toContain('.ops-no-print');
    expect(printCss).toMatch(/display:\s*none/);
    expect(printCss).toMatch(/background:\s*#fff/);
  });
});
