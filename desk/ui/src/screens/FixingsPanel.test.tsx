import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { Fixing } from '../api/types';
import FixingsPanel from './FixingsPanel';

const mocks = vi.hoisted(() => ({
  listFixings: vi.fn(),
  addFixing: vi.fn(),
  importFixingsCsv: vi.fn(),
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    listFixings: mocks.listFixings,
    addFixing: mocks.addFixing,
    importFixingsCsv: mocks.importFixingsCsv,
  };
});

const FIXINGS: Fixing[] = [
  { index: 'TIIE-F', date: '2026-11-10', value: 0.0701 },
  { index: 'USDMXN', date: '2026-11-10', value: 20.1234 },
];

beforeEach(() => {
  vi.resetAllMocks();
  mocks.listFixings.mockResolvedValue(FIXINGS);
});

describe('FixingsPanel', () => {
  it('lista las fijaciones: tasas en % y USDMXN con 4 decimales', async () => {
    render(<FixingsPanel />);
    const table = await screen.findByRole('table', { name: 'Fijaciones' });
    expect(await within(table).findByText('7.0100 %')).toBeTruthy();
    expect(within(table).getByText('20.1234')).toBeTruthy();
    expect(mocks.listFixings).toHaveBeenCalledWith({ index: undefined, from: undefined, to: undefined });
  });

  it('el encabezado de Fecha se alinea como sus celdas (a la derecha, igual que Valor)', async () => {
    render(<FixingsPanel />);
    const table = await screen.findByRole('table', { name: 'Fijaciones' });
    await within(table).findByText('7.0100 %');
    expect(within(table).getByRole('columnheader', { name: 'Fecha' }).classList.contains('num')).toBe(true);
    expect(within(table).getAllByText('2026-11-10', { selector: 'td' })[0].classList.contains('num')).toBe(true);
  });

  it('el filtro por índice y fechas llama a listFixings', async () => {
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const filters = screen.getByRole('group', { name: 'Filtro de fijaciones' });
    fireEvent.change(within(filters).getByLabelText('Índice'), { target: { value: 'SOFR' } });
    fireEvent.change(within(filters).getByLabelText('Desde'), { target: { value: '2026-11-01' } });
    fireEvent.change(within(filters).getByLabelText('Hasta'), { target: { value: '2026-11-30' } });
    await waitFor(() =>
      expect(mocks.listFixings).toHaveBeenLastCalledWith({ index: 'SOFR', from: '2026-11-01', to: '2026-11-30' }),
    );
  });

  it('el alta envía la tasa en decimal al capturar 7.01 (%)', async () => {
    mocks.addFixing.mockResolvedValue({ fixing: FIXINGS[0], created: true });
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Alta de fijación' });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2026-11-10' } });
    fireEvent.change(within(form).getByLabelText('Valor (%)'), { target: { value: '7.01' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Guardar' }));
    await waitFor(() =>
      expect(mocks.addFixing).toHaveBeenCalledWith({ index: 'TIIE-F', date: '2026-11-10', value: 0.0701 }),
    );
    expect(await screen.findByText('Fijación guardada')).toBeTruthy();
  });

  it('USDMXN se captura en MXN y se envía sin dividir', async () => {
    mocks.addFixing.mockResolvedValue({ fixing: FIXINGS[1], created: true });
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Alta de fijación' });
    fireEvent.change(within(form).getByLabelText('Índice'), { target: { value: 'USDMXN' } });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2026-11-10' } });
    fireEvent.change(within(form).getByLabelText('Valor (MXN)'), { target: { value: '20.1234' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Guardar' }));
    await waitFor(() =>
      expect(mocks.addFixing).toHaveBeenCalledWith({ index: 'USDMXN', date: '2026-11-10', value: 20.1234 }),
    );
  });

  it('muestra "Ya existía" cuando el backend responde created: false', async () => {
    mocks.addFixing.mockResolvedValue({ fixing: FIXINGS[0], created: false });
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Alta de fijación' });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2026-11-10' } });
    fireEvent.change(within(form).getByLabelText('Valor (%)'), { target: { value: '7.01' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Ya existía')).toBeTruthy();
  });

  it('un 409 del alta se muestra tal cual', async () => {
    mocks.addFixing.mockRejectedValue(new ApiError(409, 'Ya hay una fijación distinta para TIIE-F 2026-11-10', 'value'));
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Alta de fijación' });
    fireEvent.change(within(form).getByLabelText('Fecha'), { target: { value: '2026-11-10' } });
    fireEvent.change(within(form).getByLabelText('Valor (%)'), { target: { value: '7.5' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Guardar' }));
    const alert = await within(form).findByRole('alert');
    expect(alert.textContent).toBe('Ya hay una fijación distinta para TIIE-F 2026-11-10');
  });

  it('sin fecha o sin valor no llama al backend', async () => {
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Alta de fijación' });
    fireEvent.click(within(form).getByRole('button', { name: 'Guardar' }));
    expect((await within(form).findByRole('alert')).textContent).toBe('Captura la fecha y el valor');
    expect(mocks.addFixing).not.toHaveBeenCalled();
  });

  it('el CSV pegado se envía tal cual y muestra insertadas / sin cambio', async () => {
    mocks.importFixingsCsv.mockResolvedValue({ inserted: 2, unchanged: 1 });
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const csv = 'index,date,value\nTIIE-F,2026-11-10,0.0701\nSOFR,2026-11-10,0.0412\n';
    const form = screen.getByRole('form', { name: 'Importar CSV' });
    fireEvent.change(within(form).getByLabelText('CSV'), { target: { value: csv } });
    fireEvent.click(within(form).getByRole('button', { name: 'Importar' }));
    await waitFor(() => expect(mocks.importFixingsCsv).toHaveBeenCalledWith(csv));
    expect(await screen.findByText('Insertadas: 2 · Sin cambio: 1')).toBeTruthy();
  });

  it('un 400 del CSV se muestra tal cual', async () => {
    mocks.importFixingsCsv.mockRejectedValue(new ApiError(400, 'Fila 3: valor fuera de rango', 'csv'));
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Importar CSV' });
    fireEvent.change(within(form).getByLabelText('CSV'), { target: { value: 'index,date,value\n' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Importar' }));
    expect((await within(form).findByRole('alert')).textContent).toBe('Fila 3: valor fuera de rango');
  });

  it('un 409 del CSV se muestra tal cual', async () => {
    mocks.importFixingsCsv.mockRejectedValue(new ApiError(409, 'Fila 2: conflicto con una fijación guardada', 'csv'));
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Importar CSV' });
    fireEvent.change(within(form).getByLabelText('CSV'), { target: { value: 'index,date,value\nSOFR,2026-11-10,0.05\n' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Importar' }));
    expect((await within(form).findByRole('alert')).textContent).toBe('Fila 2: conflicto con una fijación guardada');
  });

  it('el archivo elegido llena el cuadro de texto con su contenido', async () => {
    render(<FixingsPanel />);
    await screen.findByText('7.0100 %');
    const form = screen.getByRole('form', { name: 'Importar CSV' });
    const text = 'index,date,value\nSOFR,2026-11-10,0.0412\n';
    const file = new File([text], 'fix.csv', { type: 'text/csv' });
    fireEvent.change(within(form).getByLabelText('Archivo'), { target: { files: [file] } });
    await waitFor(() => expect((within(form).getByLabelText('CSV') as HTMLTextAreaElement).value).toBe(text));
  });

  it('un error de listado muestra el mensaje del backend', async () => {
    mocks.listFixings.mockRejectedValue(new ApiError(400, 'Índice desconocido', 'index'));
    render(<FixingsPanel />);
    expect((await screen.findByRole('alert')).textContent).toBe('Índice desconocido');
  });
});
