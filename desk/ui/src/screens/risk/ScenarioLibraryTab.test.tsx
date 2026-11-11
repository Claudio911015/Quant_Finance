import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { ScenarioSet, SetScenariosResponse } from '../../api/riskTypes';
import type { Snapshot, Trade } from '../../api/types';
import { SnapshotProvider, useSnapshot } from '../../state/SnapshotContext';
import { ScenarioLibraryTab } from './ScenarioLibraryTab';

const mocks = vi.hoisted(() => ({
  listSnapshots: vi.fn(),
  getSnapshot: vi.fn(),
  listTrades: vi.fn(),
  listScenarioSets: vi.fn(),
  createScenarioSet: vi.fn(),
  retireScenarioSet: vi.fn(),
  runScenarioSet: vi.fn(),
}));

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    listSnapshots: mocks.listSnapshots,
    getSnapshot: mocks.getSnapshot,
    listTrades: mocks.listTrades,
  };
});

vi.mock('../../api/riskClient', () => ({
  listScenarioSets: mocks.listScenarioSets,
  createScenarioSet: mocks.createScenarioSet,
  retireScenarioSet: mocks.retireScenarioSet,
  runScenarioSet: mocks.runScenarioSet,
}));

function trade(id: number, product: string, counterparty: string): Trade {
  return {
    id,
    product,
    counterparty,
    trade_date: '2026-11-10',
    start_date: '2026-11-10',
    maturity_date: '2027-11-10',
    params: {},
    notional: 1e6,
    currency: 'MXN',
    maturity: '2027-11-10',
    created_at: '2026-11-10',
  } as unknown as Trade;
}

const TRADES = [trade(1, 'irs', 'Banco A'), trade(2, 'fx_forward', 'Banco B')];

const DEFAULT_SET: ScenarioSet = {
  id: null,
  name: 'Por omisión',
  builtin: true,
  approximation: false,
  status: 'activo',
  description: 'Los ocho escenarios de la pantalla',
  scenarios: [
    { name: 'TIIE-F +50 pb', type: 'parallel', curve: 'TIIE-F', bp: 50 },
    { name: 'SOFR steepener 25 pb', type: 'steepener', curve: 'SOFR', bp: 25 },
    { name: 'USDMXN -10 %', type: 'fx_spot', pct: -10 },
  ],
  created_at: null,
};

const MARCH_SET: ScenarioSet = {
  id: null,
  name: 'Marzo 2020',
  builtin: true,
  approximation: true,
  status: 'activo',
  description: 'Aproximación histórica: USDMXN +25 %, TIIE-F −100 pb y SOFR −150 pb a la vez',
  scenarios: [
    {
      name: 'Marzo 2020',
      type: 'combined',
      shocks: [
        { type: 'fx_spot', pct: 25 },
        { type: 'parallel', curve: 'TIIE-F', bp: -100 },
        { type: 'parallel', curve: 'SOFR', bp: -150 },
      ],
    },
  ],
  created_at: null,
};

const SAVED_SET: ScenarioSet = {
  id: 5,
  name: 'Choque Banxico',
  builtin: false,
  approximation: false,
  status: 'activo',
  description: 'Alza de tasas',
  scenarios: [{ name: 'TIIE-F +100', type: 'parallel', curve: 'TIIE-F', bp: 100 }],
  created_at: '2026-11-10T18:00:00+00:00',
};

const RUN: SetScenariosResponse = {
  snapshot: 'MX-DEMO',
  set: 'Marzo 2020',
  scenarios: [
    {
      name: 'Marzo 2020',
      total_mxn: -1234567.4,
      trades: [
        { id: 1, pnl_mxn: -1500000.2, error: null },
        { id: 2, pnl_mxn: null, error: 'Sin cotización' },
      ],
    },
  ],
};

function SwitchTo({ id }: { id: string }) {
  const { setSnapshotId } = useSnapshot();
  return <button onClick={() => setSnapshotId(id)}>cambiar a {id}</button>;
}

function renderTab() {
  return render(
    <SnapshotProvider>
      <SwitchTo id="OTRO" />
      <ScenarioLibraryTab />
    </SnapshotProvider>,
  );
}

const listCard = () => screen.getByRole('region', { name: 'Conjuntos de escenarios' });
const formCard = () => screen.getByRole('region', { name: 'Nuevo conjunto' });

/** El `<li>` de un conjunto, por el nombre de su encabezado. */
function setItem(name: string): HTMLElement {
  return within(listCard()).getByRole('heading', { name }).closest('li') as HTMLElement;
}

beforeEach(() => {
  mocks.listSnapshots.mockResolvedValue([]);
  mocks.getSnapshot.mockImplementation(async (id: string) => ({ id }) as unknown as Snapshot);
  mocks.listTrades.mockResolvedValue(TRADES);
  mocks.listScenarioSets.mockResolvedValue([DEFAULT_SET, MARCH_SET, SAVED_SET]);
  mocks.runScenarioSet.mockResolvedValue(RUN);
  mocks.createScenarioSet.mockResolvedValue(SAVED_SET);
  mocks.retireScenarioSet.mockResolvedValue({ ...SAVED_SET, status: 'baja' });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('ScenarioLibraryTab: lista', () => {
  it('rotula los de fábrica y las aproximaciones históricas, con descripción', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    expect(within(setItem('Por omisión')).getByText('De fábrica')).toBeTruthy();
    expect(within(setItem('Por omisión')).queryByText('Aproximación histórica')).toBeNull();
    expect(within(setItem('Por omisión')).getByText('Los ocho escenarios de la pantalla')).toBeTruthy();

    expect(within(setItem('Marzo 2020')).getByText('De fábrica')).toBeTruthy();
    expect(within(setItem('Marzo 2020')).getByText('Aproximación histórica')).toBeTruthy();

    expect(within(setItem('Choque Banxico')).queryByText('De fábrica')).toBeNull();
    expect(within(setItem('Choque Banxico')).queryByText('Aproximación histórica')).toBeNull();
    expect(within(setItem('Choque Banxico')).getByText('Alza de tasas')).toBeTruthy();
  });

  it('muestra cada escenario con sus choques legibles; los combinados se unen con " · "', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    const def = setItem('Por omisión');
    expect(within(def).getByText('TIIE-F +50 pb')).toBeTruthy();
    expect(within(def).getByText('SOFR steepener +25 pb')).toBeTruthy();
    expect(within(def).getByText('USDMXN −10 %')).toBeTruthy();

    expect(within(setItem('Marzo 2020')).getByText('USDMXN +25 % · TIIE-F −100 pb · SOFR −150 pb')).toBeTruthy();
    expect(within(setItem('Choque Banxico')).getByText('TIIE-F +100 pb')).toBeTruthy();
  });

  it('un error al cargar la lista se muestra', async () => {
    mocks.listScenarioSets.mockRejectedValue(new ApiError(500, 'Falla del servidor'));
    renderTab();
    expect((await within(listCard()).findByRole('alert')).textContent).toBe('Falla del servidor');
  });

  it('sin conjuntos lo dice', async () => {
    mocks.listScenarioSets.mockResolvedValue([]);
    renderTab();
    expect(await within(listCard()).findByText('Sin conjuntos.')).toBeTruthy();
  });
});

describe('ScenarioLibraryTab: correr', () => {
  it('corre el conjunto sobre el snapshot activo y arma una columna por escenario con fila de total', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fireEvent.click(within(setItem('Marzo 2020')).getByRole('button', { name: 'Correr Marzo 2020' }));

    const card = await screen.findByRole('region', { name: 'Corrida: Marzo 2020' });
    expect(mocks.runScenarioSet).toHaveBeenCalledWith('MX-DEMO', 'Marzo 2020');

    const headers = within(card).getAllByRole('columnheader').map((h) => h.textContent);
    expect(headers).toEqual(['Operación', 'Marzo 2020']);

    const row1 = within(card).getByText('#1 irs · Banco A').closest('tr') as HTMLElement;
    expect(within(row1).getByText('-1,500,000').className).toContain('scn-neg');

    // La celda que no se pudo valuar dice n/d y guarda el motivo.
    const row2 = within(card).getByText('#2 fx_forward · Banco B').closest('tr') as HTMLElement;
    const nd = within(row2).getByText('n/d');
    expect(nd.getAttribute('title')).toBe('Sin cotización');

    const total = within(card).getByText('Total').closest('tr') as HTMLElement;
    expect(within(total).getByText('-1,234,567')).toBeTruthy();
  });

  it('un error al correr se muestra en el conjunto y no deja resultado', async () => {
    mocks.runScenarioSet.mockRejectedValue(new ApiError(404, 'No existe el conjunto', 'set'));
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fireEvent.click(within(setItem('Marzo 2020')).getByRole('button', { name: 'Correr Marzo 2020' }));

    expect((await within(setItem('Marzo 2020')).findByRole('alert')).textContent).toBe('No existe el conjunto');
    expect(screen.queryByRole('region', { name: 'Corrida: Marzo 2020' })).toBeNull();
  });

  it('al cambiar de snapshot descarta el resultado anterior', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });
    fireEvent.click(within(setItem('Marzo 2020')).getByRole('button', { name: 'Correr Marzo 2020' }));
    await screen.findByRole('region', { name: 'Corrida: Marzo 2020' });

    fireEvent.click(screen.getByText('cambiar a OTRO'));

    await waitFor(() => expect(screen.queryByRole('region', { name: 'Corrida: Marzo 2020' })).toBeNull());
  });
});

describe('ScenarioLibraryTab: baja', () => {
  it('los de fábrica no tienen botón de baja; los guardados sí', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    expect(within(setItem('Por omisión')).queryByRole('button', { name: /Dar de baja/ })).toBeNull();
    expect(within(setItem('Marzo 2020')).queryByRole('button', { name: /Dar de baja/ })).toBeNull();
    expect(within(setItem('Choque Banxico')).getByRole('button', { name: 'Dar de baja Choque Banxico' })).toBeTruthy();
  });

  it('pide confirmación, da de baja por id y recarga la lista', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Choque Banxico' });
    mocks.listScenarioSets.mockResolvedValue([DEFAULT_SET, MARCH_SET]);

    fireEvent.click(within(setItem('Choque Banxico')).getByRole('button', { name: 'Dar de baja Choque Banxico' }));
    expect(mocks.retireScenarioSet).not.toHaveBeenCalled();
    expect(within(setItem('Choque Banxico')).getByText('¿Dar de baja este conjunto?')).toBeTruthy();

    fireEvent.click(within(setItem('Choque Banxico')).getByRole('button', { name: 'Confirmar baja' }));

    await waitFor(() => expect(mocks.retireScenarioSet).toHaveBeenCalledWith(5));
    await waitFor(() => expect(within(listCard()).queryByRole('heading', { name: 'Choque Banxico' })).toBeNull());
  });

  it('Cancelar no da de baja', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Choque Banxico' });

    fireEvent.click(within(setItem('Choque Banxico')).getByRole('button', { name: 'Dar de baja Choque Banxico' }));
    fireEvent.click(within(setItem('Choque Banxico')).getByRole('button', { name: 'Cancelar' }));

    expect(mocks.retireScenarioSet).not.toHaveBeenCalled();
    expect(within(setItem('Choque Banxico')).getByRole('button', { name: 'Correr Choque Banxico' })).toBeTruthy();
  });

  it('un error de la baja se muestra en el conjunto', async () => {
    mocks.retireScenarioSet.mockRejectedValue(new ApiError(409, 'El conjunto ya está de baja', 'id'));
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Choque Banxico' });

    fireEvent.click(within(setItem('Choque Banxico')).getByRole('button', { name: 'Dar de baja Choque Banxico' }));
    fireEvent.click(within(setItem('Choque Banxico')).getByRole('button', { name: 'Confirmar baja' }));

    expect((await within(setItem('Choque Banxico')).findByRole('alert')).textContent).toBe('El conjunto ya está de baja');
  });
});

describe('ScenarioLibraryTab: nuevo conjunto', () => {
  const fill = (label: string, value: string) =>
    fireEvent.change(within(formCard()).getByLabelText(label), { target: { value } });

  it('manda el cuerpo correcto con varias filas de tipos distintos', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fill('Nombre', '  Mi conjunto ');
    fill('Descripción', 'Prueba');
    fill('Nombre del escenario 1', 'SOFR +75');
    fill('Curva del escenario 1', 'SOFR');
    fill('Choque (pb) del escenario 1', '75');

    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar escenario' }));
    fill('Nombre del escenario 2', 'Rampa');
    fill('Tipo del escenario 2', 'steepener');
    fill('Choque (pb) del escenario 2', '-25');

    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar escenario' }));
    fill('Nombre del escenario 3', 'Peso débil');
    fill('Tipo del escenario 3', 'fx_spot');
    // USDMXN no lleva curva: el selector desaparece y el valor se rotula en %.
    expect(within(formCard()).queryByLabelText('Curva del escenario 3')).toBeNull();
    fill('Variación (%) del escenario 3', '12.5');

    fireEvent.click(within(formCard()).getByRole('button', { name: 'Crear conjunto' }));

    await waitFor(() =>
      expect(mocks.createScenarioSet).toHaveBeenCalledWith({
        name: 'Mi conjunto',
        description: 'Prueba',
        scenarios: [
          { name: 'SOFR +75', type: 'parallel', curve: 'SOFR', bp: 75 },
          { name: 'Rampa', type: 'steepener', curve: 'TIIE-F', bp: -25 },
          { name: 'Peso débil', type: 'fx_spot', pct: 12.5 },
        ],
      }),
    );
    // Tras crear recarga la lista y limpia el formulario.
    await waitFor(() => expect(mocks.listScenarioSets).toHaveBeenCalledTimes(2));
    await waitFor(() => expect((within(formCard()).getByLabelText('Nombre') as HTMLInputElement).value).toBe(''));
    expect(within(formCard()).queryByLabelText('Nombre del escenario 2')).toBeNull();
  });

  it('sin descripción no la manda', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fill('Nombre', 'Solo spot');
    fill('Nombre del escenario 1', 'Spot');
    fill('Tipo del escenario 1', 'fx_spot');
    fill('Variación (%) del escenario 1', '5');
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Crear conjunto' }));

    await waitFor(() =>
      expect(mocks.createScenarioSet).toHaveBeenCalledWith({
        name: 'Solo spot',
        scenarios: [{ name: 'Spot', type: 'fx_spot', pct: 5 }],
      }),
    );
  });

  it('un valor no numérico se avisa bajo los escenarios y no llama a la API', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fill('Nombre', 'X');
    fill('Nombre del escenario 1', 'A');
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Crear conjunto' }));

    expect((await within(formCard()).findByText('Escenario 1: ingresa un número válido')).id).toBe('scn-rows-error');
    expect(mocks.createScenarioSet).not.toHaveBeenCalled();
  });

  it('el 409 del nombre repetido va bajo el campo Nombre', async () => {
    mocks.createScenarioSet.mockRejectedValue(new ApiError(409, 'Ya existe un conjunto con ese nombre', 'name'));
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fill('Nombre', 'Marzo 2020');
    fill('Nombre del escenario 1', 'A');
    fill('Choque (pb) del escenario 1', '10');
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Crear conjunto' }));

    const msg = await within(formCard()).findByText('Ya existe un conjunto con ese nombre');
    expect(msg.id).toBe('scn-name-error');
    const input = within(formCard()).getByLabelText('Nombre');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('scn-name-error');
    // No es un error general.
    expect(within(formCard()).queryByRole('alert')).toBeNull();
  });

  it('el error de scenarios (con su "Escenario n") va bajo los escenarios', async () => {
    mocks.createScenarioSet.mockRejectedValue(
      new ApiError(400, "Escenario 1: 'name' debe ser texto no vacío", 'scenarios'),
    );
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fill('Nombre', 'Algo');
    fill('Choque (pb) del escenario 1', '10');
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Crear conjunto' }));

    const msg = await within(formCard()).findByText("Escenario 1: 'name' debe ser texto no vacío");
    expect(msg.id).toBe('scn-rows-error');
    expect(within(formCard()).queryByRole('alert')).toBeNull();
  });

  it('un error sin campo del formulario sale como alerta general', async () => {
    mocks.createScenarioSet.mockRejectedValue(new ApiError(500, 'Falla del servidor'));
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    fill('Nombre', 'Algo');
    fill('Nombre del escenario 1', 'A');
    fill('Choque (pb) del escenario 1', '10');
    fireEvent.click(within(formCard()).getByRole('button', { name: 'Crear conjunto' }));

    expect((await within(formCard()).findByRole('alert')).textContent).toBe('Falla del servidor');
  });

  it('agrega y quita filas; la última no se puede quitar', async () => {
    renderTab();
    await within(listCard()).findByRole('heading', { name: 'Marzo 2020' });

    const quitar1 = within(formCard()).getByRole('button', { name: 'Quitar escenario 1' }) as HTMLButtonElement;
    expect(quitar1.disabled).toBe(true);

    fireEvent.click(within(formCard()).getByRole('button', { name: 'Agregar escenario' }));
    expect(within(formCard()).getByLabelText('Nombre del escenario 2')).toBeTruthy();
    expect((within(formCard()).getByRole('button', { name: 'Quitar escenario 1' }) as HTMLButtonElement).disabled).toBe(
      false,
    );

    fireEvent.click(within(formCard()).getByRole('button', { name: 'Quitar escenario 1' }));
    expect(within(formCard()).queryByLabelText('Nombre del escenario 2')).toBeNull();
    expect(within(formCard()).getByLabelText('Nombre del escenario 1')).toBeTruthy();
  });
});
