import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { FetchFixingsResult, Fixing, FixingSource } from '../api/types';
import FixingsPanel from './FixingsPanel';

const mocks = vi.hoisted(() => ({
  listFixings: vi.fn(),
  addFixing: vi.fn(),
  importFixingsCsv: vi.fn(),
  fixingSources: vi.fn(),
  fetchFixings: vi.fn(),
  // Fecha de valuación activa (snapshot.as_of) que el panel lee del contexto.
  ctx: { snapshot: { as_of: '2026-11-11' } as { as_of: string } | null },
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    listFixings: mocks.listFixings,
    addFixing: mocks.addFixing,
    importFixingsCsv: mocks.importFixingsCsv,
    fixingSources: mocks.fixingSources,
    fetchFixings: mocks.fetchFixings,
  };
});

vi.mock('../state/SnapshotContext', () => ({
  useSnapshot: () => mocks.ctx,
}));

const FIXINGS: Fixing[] = [
  { index: 'TIIE-F', date: '2026-11-10', value: 0.0701 },
  { index: 'USDMXN', date: '2026-11-10', value: 20.1234 },
];

const NO_TOKEN = 'Falta el token de Banxico (variable BANXICO_TOKEN)';

// Con token de Banxico: los tres índices disponibles; SOFR con fijaciones hasta el 2026-11-06.
const SOURCES: FixingSource[] = [
  { index: 'TIIE-F', source: 'Banxico (SIE)', available: true, reason: null, last_date: '2026-11-10' },
  { index: 'SOFR', source: 'Fed de Nueva York', available: true, reason: null, last_date: '2026-11-06' },
  { index: 'USDMXN', source: 'Banxico (SIE)', available: true, reason: null, last_date: null },
];

function withSources(...patch: Array<Partial<FixingSource> & { index: FixingSource['index'] }>): FixingSource[] {
  return SOURCES.map((s) => ({ ...s, ...(patch.find((p) => p.index === s.index) ?? {}) }));
}

function fetched(over: Partial<FetchFixingsResult> = {}): FetchFixingsResult {
  return {
    index: 'SOFR',
    source: 'Fed de Nueva York',
    from: '2026-11-07',
    to: '2026-11-11',
    fetched: 3,
    inserted: 2,
    unchanged: 1,
    conflicts: [],
    ...over,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.ctx.snapshot = { as_of: '2026-11-11' };
  mocks.listFixings.mockResolvedValue(FIXINGS);
  mocks.fixingSources.mockResolvedValue(SOURCES);
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

  describe('Traer de la fuente', () => {
    const group = (index: string) => screen.findByRole('group', { name: `Fuente de ${index}` });

    it('muestra un botón por cada índice disponible', async () => {
      render(<FixingsPanel />);
      for (const index of ['TIIE-F', 'SOFR', 'USDMXN']) {
        const g = await group(index);
        expect((within(g).getByRole('button', { name: 'Traer de la fuente' }) as HTMLButtonElement).disabled).toBe(false);
      }
      expect(mocks.fixingSources).toHaveBeenCalledTimes(1);
    });

    it('Banxico sin token muestra el motivo en lugar del botón y SOFR sigue con botón', async () => {
      mocks.fixingSources.mockResolvedValue(
        withSources(
          { index: 'TIIE-F', available: false, reason: NO_TOKEN },
          { index: 'USDMXN', available: false, reason: NO_TOKEN },
        ),
      );
      render(<FixingsPanel />);
      for (const index of ['TIIE-F', 'USDMXN']) {
        const g = await group(index);
        expect(within(g).getByText(NO_TOKEN)).toBeTruthy();
        expect(within(g).queryByRole('button')).toBeNull();
      }
      const sofr = await group('SOFR');
      expect(within(sofr).getByRole('button', { name: 'Traer de la fuente' })).toBeTruthy();
      expect(mocks.fetchFixings).not.toHaveBeenCalled();
    });

    it('el rango va del día siguiente a la última fijación a la fecha de valuación', async () => {
      mocks.fetchFixings.mockResolvedValue(fetched());
      render(<FixingsPanel />);
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      await waitFor(() =>
        expect(mocks.fetchFixings).toHaveBeenCalledWith({ index: 'SOFR', from: '2026-11-07', to: '2026-11-11' }),
      );
    });

    it('si el rango pasa de 366 días pide solo los últimos 366 hasta la fecha de valuación y lo dice', async () => {
      mocks.fixingSources.mockResolvedValue(withSources({ index: 'SOFR', last_date: '2025-01-01' }));
      mocks.fetchFixings.mockResolvedValue(fetched({ from: '2025-11-10' }));
      render(<FixingsPanel />);
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      await waitFor(() =>
        expect(mocks.fetchFixings).toHaveBeenCalledWith({ index: 'SOFR', from: '2025-11-10', to: '2026-11-11' }),
      );
      expect((await within(g).findByRole('status')).textContent).toBe(
        'Insertadas: 2 · Sin cambio: 1 (se trajeron los últimos 366 días)',
      );
    });

    it('un rango de exactamente 366 días no se recorta ni avisa', async () => {
      mocks.fixingSources.mockResolvedValue(withSources({ index: 'SOFR', last_date: '2025-11-09' }));
      mocks.fetchFixings.mockResolvedValue(fetched({ from: '2025-11-10' }));
      render(<FixingsPanel />);
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      await waitFor(() =>
        expect(mocks.fetchFixings).toHaveBeenCalledWith({ index: 'SOFR', from: '2025-11-10', to: '2026-11-11' }),
      );
      expect((await within(g).findByRole('status')).textContent).toBe('Insertadas: 2 · Sin cambio: 1');
    });

    it('sin fijaciones previas trae los 30 días anteriores a la fecha de valuación', async () => {
      mocks.fetchFixings.mockResolvedValue(fetched({ index: 'USDMXN' }));
      render(<FixingsPanel />);
      const g = await group('USDMXN');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      await waitFor(() =>
        expect(mocks.fetchFixings).toHaveBeenCalledWith({ index: 'USDMXN', from: '2026-10-12', to: '2026-11-11' }),
      );
    });

    it('el día siguiente cruza fin de mes y de año', async () => {
      mocks.ctx.snapshot = { as_of: '2027-03-10' };
      mocks.fixingSources.mockResolvedValue(
        withSources({ index: 'SOFR', last_date: '2026-12-31' }, { index: 'TIIE-F', last_date: '2027-02-28' }),
      );
      mocks.fetchFixings.mockResolvedValue(fetched());
      render(<FixingsPanel />);
      fireEvent.click(within(await group('SOFR')).getByRole('button', { name: 'Traer de la fuente' }));
      await waitFor(() =>
        expect(mocks.fetchFixings).toHaveBeenCalledWith({ index: 'SOFR', from: '2027-01-01', to: '2027-03-10' }),
      );
      fireEvent.click(within(await group('TIIE-F')).getByRole('button', { name: 'Traer de la fuente' }));
      await waitFor(() =>
        expect(mocks.fetchFixings).toHaveBeenCalledWith({ index: 'TIIE-F', from: '2027-03-01', to: '2027-03-10' }),
      );
    });

    it('con la última fijación en la fecha de valuación o después queda "Al día" y deshabilitado', async () => {
      mocks.fixingSources.mockResolvedValue(
        withSources({ index: 'TIIE-F', last_date: '2026-11-11' }, { index: 'SOFR', last_date: '2026-11-12' }),
      );
      render(<FixingsPanel />);
      for (const index of ['TIIE-F', 'SOFR']) {
        const g = await group(index);
        const btn = within(g).getByRole('button', { name: 'Al día' }) as HTMLButtonElement;
        expect(btn.disabled).toBe(true);
        expect(within(g).queryByRole('button', { name: 'Traer de la fuente' })).toBeNull();
        fireEvent.click(btn);
      }
      expect(mocks.fetchFixings).not.toHaveBeenCalled();
    });

    it('sin snapshot cargado el botón queda deshabilitado', async () => {
      mocks.ctx.snapshot = null;
      render(<FixingsPanel />);
      const btn = within(await group('SOFR')).getByRole('button', { name: 'Traer de la fuente' }) as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
    });

    it('se deshabilita mientras corre y al terminar recarga la tabla y las fuentes', async () => {
      let resolve!: (r: FetchFixingsResult) => void;
      mocks.fetchFixings.mockReturnValue(new Promise<FetchFixingsResult>((r) => (resolve = r)));
      render(<FixingsPanel />);
      await screen.findByText('7.0100 %');
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      const running = (await within(g).findByRole('button', { name: 'Trayendo…' })) as HTMLButtonElement;
      expect(running.disabled).toBe(true);
      for (const index of ['TIIE-F', 'USDMXN']) {
        const other = within(await group(index)).getByRole('button') as HTMLButtonElement;
        expect(other.disabled).toBe(true);
      }
      expect(mocks.listFixings).toHaveBeenCalledTimes(1);
      expect(mocks.fixingSources).toHaveBeenCalledTimes(1);
      resolve(fetched());
      await within(g).findByText('Insertadas: 2 · Sin cambio: 1');
      await waitFor(() => expect(mocks.listFixings).toHaveBeenCalledTimes(2));
      expect(mocks.fixingSources).toHaveBeenCalledTimes(2);
      expect((within(g).getByRole('button', { name: 'Traer de la fuente' }) as HTMLButtonElement).disabled).toBe(false);
    });

    it('muestra insertadas, sin cambio y la tabla de conflictos con tasas en %', async () => {
      mocks.fetchFixings.mockResolvedValue(
        fetched({
          conflicts: [
            { date: '2026-11-09', stored: 0.0389, source: 0.039 },
            { date: '2026-11-10', stored: 0.0391, source: 0.0392 },
          ],
        }),
      );
      render(<FixingsPanel />);
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      expect((await within(g).findByRole('status')).textContent).toBe('Insertadas: 2 · Sin cambio: 1 · Conflictos: 2');
      const table = within(g).getByRole('table', { name: 'Conflictos de SOFR' });
      const rows = within(table).getAllByRole('row').slice(1);
      expect(rows.map((r) => Array.from(r.querySelectorAll('td')).map((td) => td.textContent))).toEqual([
        ['2026-11-09', '3.8900 %', '3.9000 %'],
        ['2026-11-10', '3.9100 %', '3.9200 %'],
      ]);
    });

    it('los conflictos de USDMXN se muestran con 4 decimales', async () => {
      mocks.fetchFixings.mockResolvedValue(
        fetched({
          index: 'USDMXN',
          source: 'Banxico (SIE)',
          inserted: 0,
          unchanged: 0,
          conflicts: [{ date: '2026-11-09', stored: 20.1, source: 20.25 }],
        }),
      );
      render(<FixingsPanel />);
      const g = await group('USDMXN');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      const table = await within(g).findByRole('table', { name: 'Conflictos de USDMXN' });
      expect(within(table).getByText('20.1000')).toBeTruthy();
      expect(within(table).getByText('20.2500')).toBeTruthy();
    });

    it('sin conflictos no muestra la tabla ni la cuenta de conflictos', async () => {
      mocks.fetchFixings.mockResolvedValue(fetched({ inserted: 0, unchanged: 3 }));
      render(<FixingsPanel />);
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      expect((await within(g).findByRole('status')).textContent).toBe('Insertadas: 0 · Sin cambio: 3');
      expect(within(g).queryByRole('table')).toBeNull();
    });

    it('un 502 de la fuente se muestra tal cual y no recarga', async () => {
      mocks.fetchFixings.mockRejectedValue(
        new ApiError(502, 'La Fed de Nueva York no respondió: HTTP Error 500: Server Error', null, null),
      );
      render(<FixingsPanel />);
      await screen.findByText('7.0100 %');
      const g = await group('SOFR');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      expect((await within(g).findByRole('alert')).textContent).toBe(
        'La Fed de Nueva York no respondió: HTTP Error 500: Server Error',
      );
      expect((within(g).getByRole('button', { name: 'Traer de la fuente' }) as HTMLButtonElement).disabled).toBe(false);
      expect(mocks.listFixings).toHaveBeenCalledTimes(1);
      expect(mocks.fixingSources).toHaveBeenCalledTimes(1);
    });

    it('un token rechazado de Banxico se muestra con el mensaje del backend', async () => {
      mocks.fetchFixings.mockRejectedValue(
        new ApiError(502, 'Banxico rechazó el token (BANXICO_TOKEN)', null, 'banxico_token_rejected'),
      );
      render(<FixingsPanel />);
      const g = await group('TIIE-F');
      fireEvent.click(within(g).getByRole('button', { name: 'Traer de la fuente' }));
      expect((await within(g).findByRole('alert')).textContent).toBe('Banxico rechazó el token (BANXICO_TOKEN)');
    });

    it('un error al cargar las fuentes se muestra y el resto del panel sigue funcionando', async () => {
      mocks.fixingSources.mockRejectedValue(new ApiError(500, 'Error 500'));
      render(<FixingsPanel />);
      expect((await screen.findByRole('alert')).textContent).toBe('Error 500');
      expect(await screen.findByText('7.0100 %')).toBeTruthy();
    });
  });
});
