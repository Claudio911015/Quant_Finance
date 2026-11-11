import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { importFpml } from '../../api/opsClient';
import { FpmlImport } from './FpmlImport';

vi.mock('../../api/opsClient', () => ({
  importFpml: vi.fn(),
}));

function renderImport() {
  return render(
    <MemoryRouter>
      <FpmlImport />
    </MemoryRouter>,
  );
}

function openPanel() {
  fireEvent.click(screen.getByRole('button', { name: 'Importar FpML' }));
}

describe('FpmlImport', () => {
  it('pegar y enviar llama importFpml con el texto', async () => {
    vi.mocked(importFpml).mockResolvedValue({
      trade: { id: 9 } as never,
      warnings: [],
    });
    renderImport();
    openPanel();
    fireEvent.change(screen.getByRole('textbox', { name: 'XML FpML' }), {
      target: { value: '<dataDocument/>' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Importar' }));
    await waitFor(() => expect(importFpml).toHaveBeenCalledWith('<dataDocument/>'));
    expect(await screen.findByText('Operación importada')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Ver operación' }).getAttribute('href')).toBe(
      '/portafolio/9',
    );
  });

  it('con avisos los muestra junto al enlace', async () => {
    vi.mocked(importFpml).mockResolvedValue({
      trade: { id: 4 } as never,
      warnings: [{ code: 'party_assumed', message: 'Se asumió party1 como la empresa' }],
    });
    renderImport();
    openPanel();
    fireEvent.change(screen.getByRole('textbox', { name: 'XML FpML' }), {
      target: { value: '<x/>' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Importar' }));
    expect(await screen.findByText('Se asumió party1 como la empresa')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Ver operación' })).toBeTruthy();
  });

  it('un 400 muestra el mensaje', async () => {
    vi.mocked(importFpml).mockRejectedValue(
      new ApiError(400, 'FpML con DTD o entidades no se acepta', 'fpml'),
    );
    renderImport();
    openPanel();
    fireEvent.change(screen.getByRole('textbox', { name: 'XML FpML' }), {
      target: { value: '<!DOCTYPE x>' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Importar' }));
    expect(await screen.findByText('FpML con DTD o entidades no se acepta')).toBeTruthy();
  });
});
