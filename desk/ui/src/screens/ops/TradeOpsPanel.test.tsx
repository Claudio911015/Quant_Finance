import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { getTradeRef, putTradeRef } from '../../api/opsClient';
import { TradeOpsPanel } from './TradeOpsPanel';

vi.mock('../../api/opsClient', () => ({
  getTradeRef: vi.fn(),
  putTradeRef: vi.fn(),
  fpmlUrl: (id: number) => `/api/trades/${id}/fpml`,
}));

function renderPanel(product: 'irs' | 'cap_floor') {
  return render(
    <MemoryRouter>
      <TradeOpsPanel tradeId={5} product={product} />
    </MemoryRouter>,
  );
}

describe('TradeOpsPanel', () => {
  beforeEach(() => {
    vi.mocked(getTradeRef).mockResolvedValue({ trade_id: 5, ref: null });
    vi.mocked(putTradeRef).mockReset();
  });

  it('con irs muestra confirmación, descarga FpML y referencia', async () => {
    renderPanel('irs');
    expect(screen.getByRole('link', { name: 'Confirmación' }).getAttribute('href')).toBe(
      '/portafolio/5/confirmacion',
    );
    expect(screen.getByRole('link', { name: 'Descargar FpML' }).getAttribute('href')).toBe(
      '/api/trades/5/fpml',
    );
    expect(screen.getByRole('button', { name: 'Editar' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('—')).toBeTruthy());
  });

  it('con cap_floor no muestra Descargar FpML', () => {
    renderPanel('cap_floor');
    expect(screen.queryByRole('link', { name: 'Descargar FpML' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Confirmación' })).toBeTruthy();
  });

  it('editar y guardar llama putTradeRef con la referencia', async () => {
    vi.mocked(putTradeRef).mockResolvedValue({ trade_id: 5, ref: 'BA-1' });
    renderPanel('irs');
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BA-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(putTradeRef).toHaveBeenCalledWith(5, 'BA-1'));
    expect(await screen.findByText('BA-1')).toBeTruthy();
  });

  it('una referencia vacía envía null', async () => {
    vi.mocked(putTradeRef).mockResolvedValue({ trade_id: 5, ref: null });
    renderPanel('irs');
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(putTradeRef).toHaveBeenCalledWith(5, null));
  });

  it('un 409 muestra el mensaje del backend', async () => {
    vi.mocked(putTradeRef).mockRejectedValue(new ApiError(409, 'Referencia repetida', 'ref'));
    renderPanel('irs');
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BA-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Referencia repetida')).toBeTruthy();
  });
});
