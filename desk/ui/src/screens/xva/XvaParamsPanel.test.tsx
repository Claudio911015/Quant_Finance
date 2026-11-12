import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { XVA_PARAMS_FIXTURE } from './fixtures';
import { XvaParamsPanel } from './XvaParamsPanel';

const mocks = vi.hoisted(() => ({ getXvaParams: vi.fn(), putXvaParams: vi.fn() }));
vi.mock('../../api/xvaClient', () => ({ getXvaParams: mocks.getXvaParams, putXvaParams: mocks.putXvaParams }));

const input = (label: string) => screen.getByLabelText(label) as HTMLInputElement;

beforeEach(() => {
  mocks.getXvaParams.mockResolvedValue(XVA_PARAMS_FIXTURE);
  mocks.putXvaParams.mockImplementation(async (body) => ({ ...XVA_PARAMS_FIXTURE, ...body, assumed: { funding_spread: false } }));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('XvaParamsPanel', () => {
  it('muestra los parámetros vigentes en las unidades del campo (pb y %)', async () => {
    render(<XvaParamsPanel onSaved={() => {}} />);
    await screen.findByLabelText('Spread de fondeo (pb)');
    expect(input('Spread de fondeo (pb)').value).toBe('50');
    expect(input('Trayectorias').value).toBe('2000');
    expect(input('Semilla').value).toBe('42');
    expect(input('Percentil de PFE (%)').value).toBe('95');
    // el spread de fondeo no está guardado: va como supuesto
    expect(screen.getByText('Supuesto')).toBeTruthy();
    expect(screen.getByText('Por omisión: 50 pb')).toBeTruthy();
  });

  it('guarda con los cuatro valores en decimales y avisa para recalcular', async () => {
    const onSaved = vi.fn();
    render(<XvaParamsPanel onSaved={onSaved} />);
    await screen.findByLabelText('Spread de fondeo (pb)');
    fireEvent.change(input('Spread de fondeo (pb)'), { target: { value: '75' } });
    fireEvent.change(input('Percentil de PFE (%)'), { target: { value: '97.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(mocks.putXvaParams).toHaveBeenCalledWith({
      funding_spread: 0.0075,
      n_paths: 2000,
      seed: 42,
      pfe_quantile: 0.975,
    });
    expect(screen.getByRole('status').textContent).toContain('Parámetros guardados');
    expect(screen.queryByText('Supuesto')).toBeNull();
  });

  it('un 400 se muestra junto al campo y no recarga', async () => {
    mocks.putXvaParams.mockRejectedValue(new ApiError(400, 'n_paths debe estar entre 100 y 20000', 'n_paths'));
    const onSaved = vi.fn();
    render(<XvaParamsPanel onSaved={onSaved} />);
    await screen.findByLabelText('Trayectorias');
    fireEvent.change(input('Trayectorias'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('n_paths debe estar entre 100 y 20000');
    expect(input('Trayectorias').getAttribute('aria-describedby')).toBe(alert.id);
    expect(input('Trayectorias').getAttribute('aria-invalid')).toBe('true');
    expect(onSaved).not.toHaveBeenCalled();
  });

  it('un valor que no es número no llega al servidor', async () => {
    render(<XvaParamsPanel onSaved={() => {}} />);
    await screen.findByLabelText('Semilla');
    fireEvent.change(input('Semilla'), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar parámetros' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Ingresa un número válido');
    expect(mocks.putXvaParams).not.toHaveBeenCalled();
  });

  it('si no carga los parámetros lo dice', async () => {
    mocks.getXvaParams.mockRejectedValue(new ApiError(500, 'falló'));
    render(<XvaParamsPanel onSaved={() => {}} />);
    expect((await screen.findByRole('alert')).textContent).toBe('falló');
  });
});
